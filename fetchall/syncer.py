"""Orquestra a varredura, o fetch paralelo e a sincronização segura.

Fluxo em duas fases, para nada acontecer sem aviso prévio:

1. ``scan_and_analyze`` — encontra os repositórios, faz fetch em paralelo e
   classifica cada um (seguro, problema ou atualizado). Nenhuma escrita.
2. ``execute_plan`` — recebe apenas os repositórios em estado seguro e
   executa pull fast-forward / push. Deve ser chamado só depois de o
   usuário revisar o plano e confirmar.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime

from .cache import save_cache
from .config import Config
from .gitrepo import (
    PROBLEM_STATES,
    RepoState,
    RepoStatus,
    analyze_repo,
    commit_all,
    pull_ff_only,
    push,
)

# Dias da semana em português para a mensagem de commit automático.
_WEEKDAYS_PT = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)
from .scanner import find_git_repos, resolve_scan_roots


@dataclass
class SyncPlan:
    """Resultado da análise, separado por destino."""

    up_to_date: list[RepoStatus] = field(default_factory=list)
    to_pull: list[RepoStatus] = field(default_factory=list)
    to_push: list[RepoStatus] = field(default_factory=list)
    problems: list[RepoStatus] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            len(self.up_to_date) + len(self.to_pull)
            + len(self.to_push) + len(self.problems)
        )

    @property
    def has_actions(self) -> bool:
        return bool(self.to_pull or self.to_push)

    @property
    def auto_commit_candidates(self) -> list[RepoStatus]:
        """Repositórios em que a ÚNICA pendência é commitar as mudanças.

        Só entram os DIRTY que não estão atrás do remoto: commitar um
        repositório atrás do remoto criaria divergência, então esses
        continuam sendo apenas reportados.
        """
        return [
            s for s in self.problems
            if s.state is RepoState.DIRTY and s.behind == 0
        ]


@dataclass
class ActionResult:
    """Resultado de um pull ou push executado."""

    status: RepoStatus
    action: str  # "pull" ou "push"
    ok: bool
    message: str


def scan_and_analyze(
    config: Config,
    on_progress: Callable[[str], None] | None = None,
    cached_repos: list | None = None,
) -> SyncPlan:
    """Encontra repositórios e classifica todos, com fetch em paralelo.

    Sem caminhos configurados, varre automaticamente todos os discos locais.
    Com ``cached_repos`` (varredura rápida), pula a busca no disco e analisa
    direto a lista dada; a varredura completa atualiza o cache ao final.
    """
    roots = resolve_scan_roots(config.scan_roots)
    if cached_repos is not None:
        repos = cached_repos
    else:
        repos = list(find_git_repos(roots, config.exclude_dirs))
        save_cache(roots, repos)
    plan = SyncPlan()
    if not repos:
        return plan

    notify = on_progress or (lambda _msg: None)
    with ThreadPoolExecutor(max_workers=max(1, config.max_workers)) as pool:
        futures = {pool.submit(analyze_repo, repo): repo for repo in repos}
        for future in as_completed(futures):
            status = future.result()
            notify(f"{status.name}: {status.state.value}")
            _classify(plan, status)

    for bucket in (plan.up_to_date, plan.to_pull, plan.to_push, plan.problems):
        bucket.sort(key=lambda s: str(s.path).lower())
    return plan


def _classify(plan: SyncPlan, status: RepoStatus) -> None:
    if status.state is RepoState.UP_TO_DATE:
        plan.up_to_date.append(status)
    elif status.state is RepoState.NEEDS_PULL:
        plan.to_pull.append(status)
    elif status.state is RepoState.NEEDS_PUSH:
        plan.to_push.append(status)
    elif status.state in PROBLEM_STATES:
        plan.problems.append(status)


def build_auto_commit_message(when: datetime | None = None) -> str:
    """Mensagem genérica e padronizada para o commit automático.

    Exemplo: ``chore: commit automático do Fetch All — sábado, 05/07/2026 14:30``.
    """
    when = when or datetime.now()
    weekday = _WEEKDAYS_PT[when.weekday()]
    return (
        "chore: commit automático do Fetch All — "
        f"{weekday}, {when.strftime('%d/%m/%Y %H:%M')}"
    )


def execute_auto_commits(
    candidates: list[RepoStatus],
    message: str,
    on_progress: Callable[[str], None] | None = None,
) -> list[ActionResult]:
    """Commita tudo nos candidatos e sincroniza (pull --ff-only + push).

    Deve receber apenas ``plan.auto_commit_candidates`` já confirmados pelo
    usuário. Se o commit falhar, o repositório não é sincronizado.
    """
    notify = on_progress or (lambda _msg: None)
    results: list[ActionResult] = []
    for status in candidates:
        ok, msg = commit_all(status, message)
        results.append(ActionResult(status, "commit", ok, msg))
        notify(f"commit {status.name}: {'ok' if ok else 'FALHOU'}")
        if not ok:
            continue
        ok, msg = pull_ff_only(status)
        results.append(ActionResult(status, "pull", ok, msg))
        notify(f"pull {status.name}: {'ok' if ok else 'FALHOU'}")
        if not ok:
            continue
        ok, msg = push(status)
        results.append(ActionResult(status, "push", ok, msg))
        notify(f"push {status.name}: {'ok' if ok else 'FALHOU'}")
    return results


def execute_plan(
    plan: SyncPlan,
    on_progress: Callable[[str], None] | None = None,
) -> list[ActionResult]:
    """Executa os pulls e pushes do plano. Não toca nos problemas."""
    notify = on_progress or (lambda _msg: None)
    results: list[ActionResult] = []
    for status in plan.to_pull:
        ok, message = pull_ff_only(status)
        results.append(ActionResult(status, "pull", ok, message))
        notify(f"pull {status.name}: {'ok' if ok else 'FALHOU'}")
    for status in plan.to_push:
        ok, message = push(status)
        results.append(ActionResult(status, "push", ok, message))
        notify(f"push {status.name}: {'ok' if ok else 'FALHOU'}")
    return results
