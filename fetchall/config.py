"""Carrega e persiste a configuração do Fetch All.

A configuração vive em ``config.json`` na raiz do projeto (ignorado pelo
git, pois contém caminhos locais). Na primeira execução o arquivo é criado
a partir dos padrões abaixo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"

# Pastas que nunca contêm repositórios do usuário ou são caras de varrer.
DEFAULT_EXCLUDES = [
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "$RECYCLE.BIN",
    "System Volume Information",
    "Windows",
    "Program Files",
    "Program Files (x86)",
    "ProgramData",
    "AppData",
]


@dataclass
class Config:
    """Configuração de varredura e sincronização."""

    scan_roots: list[str] = field(default_factory=list)
    exclude_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    max_workers: int = 8

    def to_dict(self) -> dict:
        return {
            "scan_roots": self.scan_roots,
            "exclude_dirs": self.exclude_dirs,
            "max_workers": self.max_workers,
        }


def load_config() -> Config:
    """Lê o config.json; devolve configuração padrão se ele não existir."""
    if not CONFIG_PATH.exists():
        return Config()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(
            f"config.json inválido ({exc}). Corrija ou apague o arquivo "
            "para recriar a configuração padrão."
        ) from exc
    return Config(
        scan_roots=list(data.get("scan_roots", [])),
        exclude_dirs=list(data.get("exclude_dirs", DEFAULT_EXCLUDES)),
        max_workers=int(data.get("max_workers", 8)),
    )


def save_config(config: Config) -> None:
    """Grava a configuração em config.json (UTF-8, legível)."""
    CONFIG_PATH.write_text(
        json.dumps(config.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
