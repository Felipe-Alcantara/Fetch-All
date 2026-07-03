"""Cache da última varredura, para reexecuções rápidas.

Guarda em ``scan_cache.json`` (raiz do projeto, ignorado pelo git) a lista
de repositórios encontrados e os caminhos varridos. Numa nova execução o
usuário pode pular a varredura completa do disco e ir direto à análise dos
repositórios já conhecidos — repositórios apagados são descartados na hora,
mas repositórios novos só aparecem numa varredura completa.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import PROJECT_ROOT

CACHE_PATH = PROJECT_ROOT / "scan_cache.json"


@dataclass
class ScanCache:
    """Resultado persistido de uma varredura completa."""

    scanned_at: datetime
    roots: list[str]
    repos: list[str]

    def valid_repos(self) -> list[Path]:
        """Repositórios do cache que ainda existem no disco."""
        return [
            Path(repo) for repo in self.repos if (Path(repo) / ".git").exists()
        ]

    def matches_roots(self, roots: list[str]) -> bool:
        """O cache só vale se os caminhos varridos forem os mesmos."""
        return sorted(self.roots) == sorted(roots)


def load_cache() -> ScanCache | None:
    """Lê o cache; devolve None se não existir ou estiver corrompido."""
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return ScanCache(
            scanned_at=datetime.fromisoformat(data["scanned_at"]),
            roots=list(data["roots"]),
            repos=list(data["repos"]),
        )
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return None  # cache inválido é o mesmo que cache ausente


def save_cache(roots: list[str], repos: list[Path]) -> None:
    """Grava o resultado de uma varredura completa."""
    data = {
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "roots": roots,
        "repos": [str(repo) for repo in repos],
    }
    CACHE_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
