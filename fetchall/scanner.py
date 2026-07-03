"""Varredura do disco em busca de repositórios git.

Percorre os caminhos configurados podando pastas excluídas (node_modules,
pastas de sistema etc.) e o interior de cada ``.git`` encontrado.
Repositórios aninhados (ex.: submódulos clonados) também são encontrados.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path


def list_local_drives() -> list[str]:
    """Devolve as raízes de todos os discos locais (fixos e removíveis).

    No Windows usa a API do sistema para ignorar unidades de rede e de
    CD/DVD. Em outros sistemas devolve a raiz do sistema de arquivos.
    """
    if sys.platform != "win32":
        return ["/"]
    import ctypes

    DRIVE_REMOVABLE, DRIVE_FIXED = 2, 3
    drives = []
    for drive in os.listdrives():
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
        if drive_type in (DRIVE_REMOVABLE, DRIVE_FIXED):
            drives.append(drive)
    return drives


def resolve_scan_roots(configured_roots: list[str]) -> list[str]:
    """Caminhos a varrer: os configurados ou, se vazio, todos os discos."""
    return configured_roots or list_local_drives()


def find_git_repos(scan_roots: list[str], exclude_dirs: list[str]) -> Iterator[Path]:
    """Gera o caminho de cada diretório de trabalho git sob os roots dados.

    Um repositório é qualquer pasta contendo ``.git`` (diretório ou arquivo,
    para cobrir worktrees/submódulos). A varredura não entra em ``.git`` nem
    nas pastas listadas em ``exclude_dirs`` (comparação sem diferenciar
    maiúsculas, pensada para Windows).
    """
    excludes = {name.lower() for name in exclude_dirs}
    seen: set[Path] = set()

    for root in scan_roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        for dirpath, dirnames, _filenames in os.walk(root_path, onerror=lambda _e: None):
            if ".git" in dirnames or ".git" in _filenames:
                repo = Path(dirpath).resolve()
                if repo not in seen:
                    seen.add(repo)
                    yield repo
            # Poda: não desce em .git nem em pastas excluídas.
            dirnames[:] = [
                d for d in dirnames if d != ".git" and d.lower() not in excludes
            ]
