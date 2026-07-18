"""Porta de entrada única do Fetch All — execute ``python start_app.py``."""

from __future__ import annotations

from fetchall.environment import bootstrap, check_python_version


def main() -> None:
    """Valida o ambiente e abre o menu interativo."""
    if not check_python_version():
        raise SystemExit(1)
    if not bootstrap():
        raise SystemExit(1)

    from fetchall.menu import run_menu

    run_menu()


if __name__ == "__main__":
    main()
