"""Testes do bootstrap/setup do menu de entrada.

O objetivo aqui é impedir regressão no fluxo que prepara `rich` e
`questionary`: em sistemas com PEP 668, o setup não deve tentar tratar uma
falha do pip do Python do sistema como sucesso.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import start_app


class StartAppDependencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="fetchall-start-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        patcher = mock.patch.object(start_app, "VENV_DIR", self.base / ".venv")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_install_menu_dependencies_uses_project_venv_outside_it(self) -> None:
        calls: list[list[str]] = []
        venv_python = start_app._project_venv_python()

        def fake_run(args: list[str]) -> subprocess.CompletedProcess:
            calls.append([str(arg) for arg in args])
            if args[:3] == ["/usr/bin/python3", "-m", "venv"]:
                venv_python.parent.mkdir(parents=True, exist_ok=True)
                venv_python.touch()
            return subprocess.CompletedProcess(args, 0)

        with (
            mock.patch.object(start_app.sys, "executable", "/usr/bin/python3"),
            mock.patch.object(start_app.sys, "prefix", "/usr"),
            mock.patch.object(start_app.subprocess, "run", side_effect=fake_run),
            mock.patch("builtins.print"),
        ):
            self.assertTrue(start_app._install_menu_dependencies())

        self.assertEqual(
            calls[0],
            ["/usr/bin/python3", "-m", "venv", str(start_app.VENV_DIR)],
        )
        self.assertEqual(
            calls[1],
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "rich",
                "questionary",
            ],
        )

    def test_install_menu_dependencies_reports_pip_failure(self) -> None:
        venv_python = start_app._project_venv_python()
        venv_python.parent.mkdir(parents=True, exist_ok=True)
        venv_python.touch()

        with (
            mock.patch.object(start_app.sys, "executable", "/usr/bin/python3"),
            mock.patch.object(start_app.sys, "prefix", "/usr"),
            mock.patch.object(
                start_app.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 1),
            ) as run,
            mock.patch("builtins.print"),
        ):
            self.assertFalse(start_app._install_menu_dependencies())

        run.assert_called_once_with(
            [str(venv_python), "-m", "pip", "install", "rich", "questionary"]
        )

    def test_bootstrap_decline_does_not_try_installing(self) -> None:
        with (
            mock.patch.object(start_app, "_missing_packages", return_value=["rich"]),
            mock.patch("builtins.input", return_value="n"),
            mock.patch.object(start_app, "_install_menu_dependencies") as install,
            mock.patch("builtins.print"),
        ):
            self.assertFalse(start_app._bootstrap())

        install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
