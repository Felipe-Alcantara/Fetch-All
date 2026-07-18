"""Inspeção e sincronização de um repositório git via linha de comando.

Toda ação de escrita é conservadora: pull apenas fast-forward e push
apenas quando o branch local está estritamente à frente do remoto.
Estados problemáticos são classificados e devolvidos ao chamador, que
decide como reportar — este módulo nunca tenta "resolver" nada sozinho.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .security import redact_sensitive_text

GIT_TIMEOUT_SECONDS = 120


class RepoState(Enum):
    """Estado de sincronização de um repositório após o fetch."""

    UP_TO_DATE = "Atualizado"
    NEEDS_PULL = "Precisa de pull"
    NEEDS_PUSH = "Precisa de push"
    DIVERGED = "Divergiu do remoto"
    DIRTY = "Mudanças não commitadas"
    CONFLICT = "Merge/rebase em andamento"
    NO_REMOTE = "Sem remoto configurado"
    NO_UPSTREAM = "Branch sem upstream"
    DETACHED = "HEAD desanexado"
    FETCH_ERROR = "Erro no fetch"
    GIT_ERROR = "Erro do git"


# Estados que o sincronizador pode resolver com segurança.
SAFE_STATES = {RepoState.NEEDS_PULL, RepoState.NEEDS_PUSH}
# Estados que exigem intervenção manual e são apenas reportados.
PROBLEM_STATES = {
    RepoState.DIVERGED,
    RepoState.DIRTY,
    RepoState.CONFLICT,
    RepoState.NO_REMOTE,
    RepoState.NO_UPSTREAM,
    RepoState.DETACHED,
    RepoState.FETCH_ERROR,
    RepoState.GIT_ERROR,
}


@dataclass
class RepoStatus:
    """Resultado da análise de um repositório."""

    path: Path
    state: RepoState
    branch: str = ""
    ahead: int = 0
    behind: int = 0
    detail: str = ""
    dirty_files: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.path.name


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Executa um comando git dentro do repositório, sem prompts interativos."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=GIT_TIMEOUT_SECONDS,
        env=_non_interactive_env(),
    )


def _non_interactive_env() -> dict[str, str]:
    """Ambiente que impede o git de abrir prompts de credencial no console."""
    import os

    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _git_action(repo: Path, *args: str) -> tuple[subprocess.CompletedProcess[str] | None, str]:
    """Executa uma ação Git e transforma falhas de processo em resultado seguro."""
    try:
        return _git(repo, *args), ""
    except subprocess.TimeoutExpired:
        return None, "git excedeu o tempo limite; confirme o estado e tente novamente"
    except OSError as exc:
        return None, redact_sensitive_text(str(exc))


def analyze_repo(repo: Path, do_fetch: bool = True) -> RepoStatus:
    """Faz fetch (opcional) e classifica o estado do repositório."""
    try:
        return _analyze(repo, do_fetch)
    except subprocess.TimeoutExpired:
        return RepoStatus(repo, RepoState.GIT_ERROR, detail="git excedeu o tempo limite")
    except OSError as exc:
        return RepoStatus(repo, RepoState.GIT_ERROR, detail=redact_sensitive_text(str(exc)))


def _analyze(repo: Path, do_fetch: bool) -> RepoStatus:
    # Merge/rebase/cherry-pick inacabado tem prioridade sobre tudo.
    git_dir_proc = _git(repo, "rev-parse", "--git-dir")
    if git_dir_proc.returncode != 0:
        return RepoStatus(
            repo,
            RepoState.GIT_ERROR,
            detail=redact_sensitive_text(git_dir_proc.stderr.strip()),
        )
    git_dir = repo / git_dir_proc.stdout.strip()
    for marker in (
        "MERGE_HEAD",
        "REBASE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "rebase-apply",
        "rebase-merge",
    ):
        if (git_dir / marker).exists():
            return RepoStatus(repo, RepoState.CONFLICT, detail=f"{marker} presente")

    branch_proc = _git(repo, "symbolic-ref", "--short", "-q", "HEAD")
    if branch_proc.returncode != 0:
        return RepoStatus(repo, RepoState.DETACHED)
    branch = branch_proc.stdout.strip()

    remote_proc = _git(repo, "remote")
    if remote_proc.returncode != 0:
        return RepoStatus(
            repo,
            RepoState.GIT_ERROR,
            branch=branch,
            detail=redact_sensitive_text(remote_proc.stderr.strip()),
        )
    remotes = remote_proc.stdout.split()
    if not remotes:
        return RepoStatus(repo, RepoState.NO_REMOTE, branch=branch)

    if do_fetch:
        fetch = _git(repo, "fetch", "--all", "--prune")
        if fetch.returncode != 0:
            return RepoStatus(
                repo,
                RepoState.FETCH_ERROR,
                branch=branch,
                detail=(
                    redact_sensitive_text(fetch.stderr.strip()).splitlines()[-1]
                    if fetch.stderr.strip()
                    else ""
                ),
            )

    status_proc = _git(repo, "status", "--porcelain")
    if status_proc.returncode != 0:
        return RepoStatus(
            repo,
            RepoState.GIT_ERROR,
            branch=branch,
            detail=redact_sensitive_text(status_proc.stderr.strip()),
        )
    dirty_files = [line for line in status_proc.stdout.splitlines() if line.strip()]

    upstream = _git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream.returncode != 0:
        return RepoStatus(
            repo,
            RepoState.NO_UPSTREAM,
            branch=branch,
            dirty_files=dirty_files,
            detail=f"branch '{branch}' não rastreia nenhum branch remoto",
        )

    counts = _git(repo, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    if counts.returncode != 0:
        return RepoStatus(
            repo,
            RepoState.GIT_ERROR,
            branch=branch,
            detail=redact_sensitive_text(counts.stderr.strip()),
        )
    try:
        behind, ahead = (int(n) for n in counts.stdout.split())
    except ValueError:
        return RepoStatus(
            repo,
            RepoState.GIT_ERROR,
            branch=branch,
            detail="git retornou contadores de commits inválidos",
        )

    if dirty_files:
        return RepoStatus(
            repo,
            RepoState.DIRTY,
            branch=branch,
            ahead=ahead,
            behind=behind,
            dirty_files=dirty_files,
            detail=f"{len(dirty_files)} arquivo(s) modificados/não rastreados",
        )
    if ahead and behind:
        return RepoStatus(
            repo,
            RepoState.DIVERGED,
            branch=branch,
            ahead=ahead,
            behind=behind,
            detail="local e remoto têm commits diferentes; resolva manualmente",
        )
    if behind:
        return RepoStatus(repo, RepoState.NEEDS_PULL, branch=branch, behind=behind)
    if ahead:
        return RepoStatus(repo, RepoState.NEEDS_PUSH, branch=branch, ahead=ahead)
    return RepoStatus(repo, RepoState.UP_TO_DATE, branch=branch)


def pull_ff_only(status: RepoStatus) -> tuple[bool, str]:
    """Pull fast-forward; nunca cria merge nem toca em repositório sujo."""
    proc, error = _git_action(status.path, "pull", "--ff-only")
    if proc is None:
        return False, error
    ok = proc.returncode == 0
    return ok, redact_sensitive_text(proc.stdout if ok else proc.stderr).strip()


def commit_all(status: RepoStatus, message: str) -> tuple[bool, str]:
    """Adiciona tudo (``git add -A``) e cria um commit com a mensagem dada.

    Usado apenas no fluxo de commit automático, com confirmação explícita
    do usuário; nunca é chamado sem o repositório estar em estado DIRTY.
    """
    add, error = _git_action(status.path, "add", "-A")
    if add is None:
        return False, error
    if add.returncode != 0:
        return False, redact_sensitive_text(add.stderr.strip())
    proc, error = _git_action(status.path, "commit", "-m", message)
    if proc is None:
        return False, error
    ok = proc.returncode == 0
    return ok, redact_sensitive_text(proc.stdout + proc.stderr).strip()


def push(status: RepoStatus) -> tuple[bool, str]:
    """Push simples do branch atual para o upstream já configurado."""
    proc, error = _git_action(status.path, "push")
    if proc is None:
        return False, error
    ok = proc.returncode == 0
    return ok, redact_sensitive_text(proc.stdout + proc.stderr).strip()
