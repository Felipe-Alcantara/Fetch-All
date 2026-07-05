"""Testes do registro em Markdown das passadas de sincronização."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from fetchall.gitrepo import RepoState, RepoStatus
from fetchall.runlog import build_run_report, write_run_report
from fetchall.syncer import ActionResult, SyncPlan

WHEN = datetime(2026, 7, 5, 14, 30, 0)


def _status(name: str, state: RepoState, **kwargs) -> RepoStatus:
    return RepoStatus(path=Path(f"/tmp/{name}"), state=state, branch="main", **kwargs)


class BuildRunReportTests(unittest.TestCase):
    def test_executed_run_lists_done_saved_and_pending(self) -> None:
        pull = _status("a", RepoState.NEEDS_PULL, behind=2)
        push = _status("b", RepoState.NEEDS_PUSH, ahead=1)
        problem = _status("c", RepoState.DIRTY, detail="2 arquivo(s)")
        plan = SyncPlan(to_pull=[pull], to_push=[push], problems=[problem])
        results = [
            ActionResult(pull, "pull", True, "ok"),
            ActionResult(push, "push", True, "ok"),
        ]
        text = build_run_report(plan, results, executed=True, scan_mode="completa", when=WHEN)
        self.assertIn("Passada de 05/07/2026 14:30:00", text)
        self.assertIn("pull concluído", text)
        self.assertIn("push enviado ao remoto", text)
        self.assertIn(RepoState.DIRTY.value, text)
        self.assertIn("1 item(ns) exigem atenção manual", text)

    def test_cancelled_run_reports_planned_actions_as_not_done(self) -> None:
        pull = _status("a", RepoState.NEEDS_PULL, behind=1)
        plan = SyncPlan(to_pull=[pull])
        text = build_run_report(plan, [], executed=False, scan_mode="rápida (cache)", when=WHEN)
        self.assertIn("Nada foi executado", text)
        self.assertIn("pull planejado, não executado", text)
        self.assertIn("Nenhum push nesta passada", text)

    def test_clean_run_has_no_pending(self) -> None:
        plan = SyncPlan(up_to_date=[_status("a", RepoState.UP_TO_DATE)])
        text = build_run_report(plan, [], executed=False, scan_mode="completa", when=WHEN)
        self.assertIn("Nenhuma pendência", text)
        self.assertIn("Nada ficou de fora", text)

    def test_failed_action_appears_as_not_done(self) -> None:
        push = _status("b", RepoState.NEEDS_PUSH, ahead=1)
        plan = SyncPlan(to_push=[push])
        results = [ActionResult(push, "push", False, "erro de rede")]
        text = build_run_report(plan, results, executed=True, scan_mode="completa", when=WHEN)
        self.assertIn("push FALHOU: erro de rede", text)
        self.assertIn("1 item(ns) exigem atenção manual", text)


    def test_auto_committed_repo_is_not_listed_as_pending(self) -> None:
        dirty = _status("a", RepoState.DIRTY, detail="1 arquivo(s)")
        plan = SyncPlan(problems=[dirty])
        results = [
            ActionResult(dirty, "commit", True, "ok"),
            ActionResult(dirty, "pull", True, "ok"),
            ActionResult(dirty, "push", True, "ok"),
        ]
        text = build_run_report(plan, results, executed=True, scan_mode="completa", when=WHEN)
        self.assertIn("commit concluído", text)
        self.assertIn("push enviado ao remoto", text)
        self.assertIn("Nenhuma pendência", text)
        self.assertNotIn(RepoState.DIRTY.value, text)


class WriteRunReportTests(unittest.TestCase):
    def test_writes_file_named_by_timestamp(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="fetchall-runlog-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        plan = SyncPlan()
        path = write_run_report(plan, [], False, "completa", when=WHEN, runs_dir=base)
        self.assertEqual(path.name, "2026-07-05_14-30-00.md")
        self.assertIn("Passada de 05/07/2026", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
