"""Executa localmente as mesmas verificações obrigatórias da integração contínua."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run(label: str, command: list[str]) -> None:
    """Executa uma etapa e interrompe com o mesmo código em caso de falha."""
    print(f"\n==> {label}", flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-audit",
        action="store_true",
        help="pula a consulta de vulnerabilidades (útil quando estiver offline)",
    )
    args = parser.parse_args()

    python = sys.executable
    _run(
        "Compilação",
        [python, "-m", "compileall", "-q", "start_app.py", "fetchall", "tests"],
    )
    _run("Consistência das dependências", [python, "-m", "pip", "check"])
    _run("Lint", [python, "-m", "ruff", "check", "."])
    _run("Formatação", [python, "-m", "ruff", "format", "--check", "."])
    _run("Links da documentação", [python, "scripts/check_markdown_links.py"])
    _run(
        "Testes e cobertura",
        [
            python,
            "-m",
            "coverage",
            "run",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v",
        ],
    )
    _run("Relatório de cobertura", [python, "-m", "coverage", "report"])
    if not args.skip_audit:
        _run(
            "Auditoria das dependências de execução",
            [
                python,
                "-m",
                "pip_audit",
                "-r",
                "requirements.lock",
                "--disable-pip",
            ],
        )
        _run(
            "Auditoria das ferramentas de desenvolvimento",
            [
                python,
                "-m",
                "pip_audit",
                "-r",
                "requirements-dev.lock",
                "--disable-pip",
            ],
        )

    print("\nTodas as verificações passaram.")


if __name__ == "__main__":
    main()
