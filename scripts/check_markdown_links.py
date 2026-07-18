"""Falha quando um link Markdown relativo aponta para um arquivo inexistente."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRECTORIES = {
    ".git",
    ".venv",
    "Padrão de qualidade - Felixo System Design",
    "passadas",
}
LINK_PATTERN = re.compile(r"!?\[[^]]*]\(([^)]+)\)")


def _markdown_files() -> list[Path]:
    return [
        path
        for path in PROJECT_ROOT.rglob("*.md")
        if not SKIP_DIRECTORIES.intersection(path.relative_to(PROJECT_ROOT).parts)
    ]


def main() -> None:
    broken: list[str] = []
    for document in _markdown_files():
        text = document.read_text(encoding="utf-8")
        for raw_target in LINK_PATTERN.findall(text):
            raw_target = raw_target.strip()
            if raw_target.startswith("<") and ">" in raw_target:
                target = raw_target[1:].split(">", 1)[0]
            else:
                target = raw_target.split(maxsplit=1)[0]
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            relative_path = unquote(target.split("#", 1)[0])
            if relative_path and not (document.parent / relative_path).resolve().exists():
                broken.append(f"{document.relative_to(PROJECT_ROOT)} -> {target}")

    if broken:
        print("Links locais quebrados:")
        print("\n".join(f"- {item}" for item in broken))
        raise SystemExit(1)
    print(f"Links locais válidos em {len(_markdown_files())} arquivo(s) Markdown.")


if __name__ == "__main__":
    main()
