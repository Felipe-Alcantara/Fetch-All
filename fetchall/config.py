"""Carrega e persiste a configuração do Fetch All.

A configuração vive em ``config.json`` na raiz do projeto (ignorado pelo
git, pois contém caminhos locais). Na primeira execução o arquivo é criado
a partir dos padrões abaixo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .storage import atomic_write_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"

# Pastas que nunca contêm repositórios do usuário ou são caras de varrer.
# Inclui caches de ferramentas de IA (.gemini, .codex, .claude) e bibliotecas
# Steam, que criam repositórios git internos que só geram ruído no relatório.
DEFAULT_EXCLUDES = [
    ".gemini",
    ".codex",
    ".claude",
    "SteamLibrary",
    "steamapps",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    # Windows: lixeira e pastas de sistema/programas.
    "$RECYCLE.BIN",
    "System Volume Information",
    "Windows",
    "Program Files",
    "Program Files (x86)",
    "ProgramData",
    "AppData",
    # Linux/macOS: lixeiras, caches (ex.: ~/.cache/pre-commit clona
    # repositórios git internos) e pastas de sistema.
    "lost+found",
    ".cache",
    "snap",
    ".Trash",
    ".Trashes",
]


@dataclass
class Config:
    """Configuração de varredura e sincronização."""

    scan_roots: list[str] = field(default_factory=list)
    exclude_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    max_workers: int = 8

    def to_dict(self) -> dict[str, object]:
        return {
            "scan_roots": self.scan_roots,
            "exclude_dirs": self.exclude_dirs,
            "max_workers": self.max_workers,
        }


def _string_list(data: dict[str, object], field_name: str) -> list[str]:
    """Valida uma lista de strings vinda do arquivo de configuração."""
    value = data.get(field_name, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"'{field_name}' deve ser uma lista de textos não vazios")
    return value


def _max_workers(data: dict[str, object]) -> int:
    """Valida o limite de concorrência sem aceitar bool ou valores abusivos."""
    value = data.get("max_workers", 8)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 256:
        raise ValueError("'max_workers' deve ser um inteiro entre 1 e 256")
    return value


def _config_from_data(data: object) -> Config:
    """Converte JSON externo em configuração depois de validar seu esquema."""
    if not isinstance(data, dict):
        raise ValueError("a raiz deve ser um objeto JSON")
    scan_roots = _string_list(data, "scan_roots")
    saved_excludes = _string_list(data, "exclude_dirs")
    merged_excludes = list(
        dict.fromkeys(
            [
                *saved_excludes,
                *(name for name in DEFAULT_EXCLUDES if name not in saved_excludes),
            ]
        )
    )
    return Config(
        scan_roots=scan_roots,
        exclude_dirs=merged_excludes,
        max_workers=_max_workers(data),
    )


def load_config() -> Config:
    """Lê o config.json; devolve configuração padrão se ele não existir."""
    if not CONFIG_PATH.exists():
        return Config()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return _config_from_data(data)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        raise ValueError(
            f"config.json inválido ({exc}). Corrija ou apague o arquivo "
            "para recriar a configuração padrão."
        ) from exc


def save_config(config: Config) -> None:
    """Grava a configuração em config.json (UTF-8, legível)."""
    validated = _config_from_data(config.to_dict())
    atomic_write_text(
        CONFIG_PATH,
        json.dumps(validated.to_dict(), indent=2, ensure_ascii=False) + "\n",
    )
