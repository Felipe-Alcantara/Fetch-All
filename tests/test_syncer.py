"""Testes da orquestração entre scanner, análise e ações Git."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from fetchall import syncer
from fetchall.config import Config
from fetchall.gitrepo import RepoState, RepoStatus


def _status(name: str, state: RepoState, **kwargs) -> RepoStatus:
    return RepoStatus(Path(f"/repos/{name}"), state, branch="main", **kwargs)


class ScanAndAnalyzeTests(unittest.TestCase):
    def test_full_scan_updates_cache_classifies_and_reports_progress(self) -> None:
        statuses = {
            Path("/repos/a"): _status("a", RepoState.UP_TO_DATE),
            Path("/repos/b"): _status("b", RepoState.NEEDS_PULL, behind=1),
            Path("/repos/c"): _status("c", RepoState.NEEDS_PUSH, ahead=2),
            Path("/repos/d"): _status("d", RepoState.DIRTY),
        }
        progress: list[str] = []
        with (
            mock.patch.object(syncer, "resolve_scan_roots", return_value=["/repos"]),
            mock.patch.object(syncer, "find_git_repos", return_value=iter(statuses)),
            mock.patch.object(syncer, "save_cache") as save_cache,
            mock.patch.object(syncer, "analyze_repo", side_effect=lambda path: statuses[path]),
        ):
            plan = syncer.scan_and_analyze(
                Config(scan_roots=["/repos"], max_workers=2),
                on_progress=progress.append,
            )

        self.assertEqual(plan.total, 4)
        self.assertEqual([item.name for item in plan.to_pull], ["b"])
        self.assertEqual([item.name for item in plan.to_push], ["c"])
        self.assertEqual([item.name for item in plan.problems], ["d"])
        self.assertEqual(len(progress), 4)
        save_cache.assert_called_once_with(["/repos"], list(statuses))

    def test_cached_scan_does_not_walk_disks_or_rewrite_cache(self) -> None:
        repo = Path("/repos/a")
        with (
            mock.patch.object(syncer, "resolve_scan_roots", return_value=["/repos"]),
            mock.patch.object(syncer, "find_git_repos") as find_repos,
            mock.patch.object(syncer, "save_cache") as save_cache,
            mock.patch.object(
                syncer,
                "analyze_repo",
                return_value=_status("a", RepoState.UP_TO_DATE),
            ),
        ):
            plan = syncer.scan_and_analyze(Config(), cached_repos=[repo])

        self.assertEqual(plan.total, 1)
        find_repos.assert_not_called()
        save_cache.assert_not_called()


class ExecutePlanTests(unittest.TestCase):
    def test_fresh_safe_states_execute_planned_pull_and_push(self) -> None:
        planned_pull = _status("a", RepoState.NEEDS_PULL, behind=1)
        planned_push = _status("b", RepoState.NEEDS_PUSH, ahead=1)
        fresh_pull = _status("a", RepoState.NEEDS_PULL, behind=1)
        fresh_push = _status("b", RepoState.NEEDS_PUSH, ahead=1)
        plan = syncer.SyncPlan(to_pull=[planned_pull], to_push=[planned_push])
        with (
            mock.patch.object(syncer, "analyze_repo", side_effect=[fresh_pull, fresh_push]),
            mock.patch.object(syncer, "pull_ff_only", return_value=(True, "ok")) as pull,
            mock.patch.object(syncer, "push", return_value=(True, "ok")) as push,
        ):
            results = syncer.execute_plan(plan)

        self.assertEqual([result.action for result in results], ["pull", "push"])
        self.assertTrue(all(result.ok for result in results))
        pull.assert_called_once_with(fresh_pull)
        push.assert_called_once_with(fresh_push)


class AutoCommitGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planned = _status("a", RepoState.DIRTY)
        self.fresh_dirty = _status("a", RepoState.DIRTY)
        self.needs_push = _status("a", RepoState.NEEDS_PUSH, ahead=1)

    def test_state_change_after_commit_stops_before_pull(self) -> None:
        diverged = _status("a", RepoState.DIVERGED, ahead=1, behind=1)
        with (
            mock.patch.object(syncer, "analyze_repo", side_effect=[self.fresh_dirty, diverged]),
            mock.patch.object(syncer, "commit_all", return_value=(True, "ok")),
            mock.patch.object(syncer, "pull_ff_only") as pull,
        ):
            results = syncer.execute_auto_commits([self.planned], "chore: teste")

        self.assertEqual([result.action for result in results], ["commit", "pull"])
        self.assertFalse(results[-1].ok)
        pull.assert_not_called()

    def test_pull_failure_stops_before_push(self) -> None:
        with (
            mock.patch.object(
                syncer,
                "analyze_repo",
                side_effect=[self.fresh_dirty, self.needs_push],
            ),
            mock.patch.object(syncer, "commit_all", return_value=(True, "ok")),
            mock.patch.object(syncer, "pull_ff_only", return_value=(False, "falhou")),
            mock.patch.object(syncer, "push") as push,
        ):
            results = syncer.execute_auto_commits([self.planned], "chore: teste")

        self.assertFalse(results[-1].ok)
        push.assert_not_called()

    def test_state_change_after_pull_stops_before_push(self) -> None:
        diverged = _status("a", RepoState.DIVERGED, ahead=1, behind=1)
        with (
            mock.patch.object(
                syncer,
                "analyze_repo",
                side_effect=[self.fresh_dirty, self.needs_push, diverged],
            ),
            mock.patch.object(syncer, "commit_all", return_value=(True, "ok")),
            mock.patch.object(syncer, "pull_ff_only", return_value=(True, "ok")),
            mock.patch.object(syncer, "push") as push,
        ):
            results = syncer.execute_auto_commits([self.planned], "chore: teste")

        self.assertEqual([result.action for result in results], ["commit", "pull", "push"])
        self.assertFalse(results[-1].ok)
        push.assert_not_called()


if __name__ == "__main__":
    unittest.main()
