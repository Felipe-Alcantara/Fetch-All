"""Utilitários de teste: criação de repositórios git temporários e locais.

Os testes nunca tocam a rede: o "remoto" é sempre um repositório bare em
pasta temporária, então fetch/pull/push funcionam offline e são seguros.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# Identidade fixa para os commits de teste, sem depender do git config global.
GIT_ID = [
    "-c",
    "user.name=Teste",
    "-c",
    "user.email=teste@example.com",
    "-c",
    "commit.gpgsign=false",
]


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Roda git no repositório dado e falha alto se o comando falhar."""
    proc = subprocess.run(
        ["git", *GIT_ID, "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} falhou: {proc.stderr}")
    return proc


def make_remote_and_clone(base: Path, name: str = "projeto") -> tuple[Path, Path]:
    """Cria um remoto bare + um clone com um commit inicial já enviado."""
    remote = base / f"{name}-remote.git"
    remote.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(remote)],
        capture_output=True,
        check=True,
    )
    clone = base / name
    subprocess.run(
        ["git", "clone", str(remote), str(clone)],
        capture_output=True,
        check=True,
    )
    commit(clone, "inicial.txt", "conteúdo inicial")
    git(clone, "push", "-u", "origin", "main")
    return remote, clone


def commit(repo: Path, filename: str, content: str, message: str = "commit de teste") -> None:
    """Cria/edita um arquivo e commita."""
    (repo / filename).write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)
