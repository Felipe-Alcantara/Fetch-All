"""Testes do bootstrap isolado e da porta de entrada do aplicativo."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import start_app
from fetchall import environment


class EnvironmentDependencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="fetchall-start-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        patcher = mock.patch.object(environment, "VENV_DIR", self.base / ".venv")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_install_menu_dependencies_uses_project_venv_outside_it(self) -> None:
        calls: list[list[str]] = []
        venv_python = environment.project_venv_python()

        def fake_run(args: list[str]) -> subprocess.CompletedProcess:
            calls.append([str(arg) for arg in args])
            if args[:3] == ["/usr/bin/python3", "-m", "venv"]:
                venv_python.parent.mkdir(parents=True, exist_ok=True)
                venv_python.touch()
            return subprocess.CompletedProcess(args, 0)

        with (
            mock.patch.object(environment.sys, "executable", "/usr/bin/python3"),
            mock.patch.object(environment.sys, "prefix", "/usr"),
            mock.patch.object(environment.subprocess, "run", side_effect=fake_run),
            mock.patch("builtins.print"),
        ):
            self.assertTrue(environment.install_menu_dependencies())

        self.assertEqual(calls[0], ["/usr/bin/python3", "-m", "venv", str(environment.VENV_DIR)])
        self.assertEqual(
            calls[1],
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--requirement",
                str(environment.REQUIREMENTS_LOCK),
            ],
        )

    def test_install_menu_dependencies_reports_pip_failure(self) -> None:
        venv_python = environment.project_venv_python()
        venv_python.parent.mkdir(parents=True, exist_ok=True)
        venv_python.touch()

        with (
            mock.patch.object(environment.sys, "executable", "/usr/bin/python3"),
            mock.patch.object(environment.sys, "prefix", "/usr"),
            mock.patch.object(
                environment.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 1),
            ) as run,
            mock.patch("builtins.print"),
        ):
            self.assertFalse(environment.install_menu_dependencies())

        run.assert_called_once_with(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--requirement",
                str(environment.REQUIREMENTS_LOCK),
            ]
        )

    def test_bootstrap_relaunches_via_subprocess_not_execv(self) -> None:
        with (
            mock.patch.object(environment, "missing_packages", return_value=["rich"]),
            mock.patch("builtins.input", return_value="s"),
            mock.patch.object(environment, "install_menu_dependencies", return_value=True),
            mock.patch.object(environment, "uses_project_venv", return_value=False),
            mock.patch.object(
                environment.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0),
            ) as run,
            mock.patch("builtins.print"),
            self.assertRaises(SystemExit) as error,
        ):
            environment.bootstrap()

        self.assertEqual(error.exception.code, 0)
        args = run.call_args[0][0]
        self.assertEqual(args[0], str(environment.project_venv_python()))
        self.assertTrue(args[1].endswith("start_app.py"))

    def test_old_python_is_rejected_with_clear_message(self) -> None:
        with (
            mock.patch.object(environment.sys, "version_info", (3, 8, 0)),
            mock.patch("builtins.print") as fake_print,
        ):
            self.assertFalse(environment.check_python_version())
        printed = " ".join(str(call.args[0]) for call in fake_print.call_args_list)
        self.assertIn("3.10", printed)

    def test_current_python_is_accepted(self) -> None:
        self.assertTrue(environment.check_python_version())

    def test_bootstrap_decline_does_not_try_installing(self) -> None:
        with (
            mock.patch.object(environment, "missing_packages", return_value=["rich"]),
            mock.patch("builtins.input", return_value="n"),
            mock.patch.object(environment, "install_menu_dependencies") as install,
            mock.patch("builtins.print"),
        ):
            self.assertFalse(environment.bootstrap())
        install.assert_not_called()

    def test_outdated_dependency_is_reported_as_missing(self) -> None:
        with mock.patch.object(environment, "version", return_value="0.0.1"):
            self.assertIn("rich", environment.missing_packages(("rich",)))

    def test_bootstrap_versions_match_direct_requirements(self) -> None:
        declared = {}
        lines = (
            (environment.PROJECT_ROOT / "requirements.in").read_text(encoding="utf-8").splitlines()
        )
        for line in lines:
            if line and not line.startswith("#"):
                package, package_version = line.split("==", 1)
                declared[package] = package_version
        self.assertEqual(environment.REQUIRED_VERSIONS, declared)


class StartAppEntryPointTests(unittest.TestCase):
    def test_main_opens_menu_after_successful_bootstrap(self) -> None:
        with (
            mock.patch.object(start_app, "check_python_version", return_value=True),
            mock.patch.object(start_app, "bootstrap", return_value=True),
            mock.patch("fetchall.menu.run_menu") as run_menu,
        ):
            start_app.main()
        run_menu.assert_called_once_with()

    def test_main_stops_when_python_is_unsupported(self) -> None:
        with (
            mock.patch.object(start_app, "check_python_version", return_value=False),
            self.assertRaises(SystemExit) as error,
        ):
            start_app.main()
        self.assertEqual(error.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
