"""Testes da classificação de estados — o coração da segurança do programa.

Cada teste monta um par remoto bare + clone em pasta temporária (offline)
e verifica que `analyze_repo` classifica o estado corretamente, em especial
os estados problemáticos que nunca podem virar ação automática.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from fetchall import syncer
from fetchall.gitrepo import RepoState, RepoStatus, analyze_repo, pull_ff_only, push
from tests.helpers import commit, git, make_remote_and_clone


class GitRepoStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="fetchall-test-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.remote, self.clone = make_remote_and_clone(self.base)

    def _second_clone(self) -> Path:
        """Outro clone do mesmo remoto, para simular commits vindos de fora."""
        import subprocess

        other = self.base / "outro-clone"
        subprocess.run(
            ["git", "clone", str(self.remote), str(other)],
            capture_output=True, check=True,
        )
        return other

    def test_up_to_date(self) -> None:
        status = analyze_repo(self.clone)
        self.assertIs(status.state, RepoState.UP_TO_DATE)
        self.assertEqual(status.branch, "main")

    def test_needs_push(self) -> None:
        commit(self.clone, "novo.txt", "mudança local")
        status = analyze_repo(self.clone)
        self.assertIs(status.state, RepoState.NEEDS_PUSH)
        self.assertEqual(status.ahead, 1)

    def test_needs_pull(self) -> None:
        other = self._second_clone()
        commit(other, "remoto.txt", "mudança de outra máquina")
        git(other, "push")
        status = analyze_repo(self.clone)
        self.assertIs(status.state, RepoState.NEEDS_PULL)
        self.assertEqual(status.behind, 1)

    def test_diverged_is_problem(self) -> None:
        other = self._second_clone()
        commit(other, "remoto.txt", "mudança de fora")
        git(other, "push")
        commit(self.clone, "local.txt", "mudança local")
        status = analyze_repo(self.clone)
        self.assertIs(status.state, RepoState.DIVERGED)
        self.assertEqual((status.ahead, status.behind), (1, 1))

    def test_dirty_is_problem_even_if_behind(self) -> None:
        other = self._second_clone()
        commit(other, "remoto.txt", "mudança de fora")
        git(other, "push")
        (self.clone / "sujo.txt").write_text("não commitado", encoding="utf-8")
        status = analyze_repo(self.clone)
        self.assertIs(status.state, RepoState.DIRTY)
        self.assertEqual(len(status.dirty_files), 1)

    def test_no_remote(self) -> None:
        git(self.clone, "remote", "remove", "origin")
        status = analyze_repo(self.clone, do_fetch=False)
        self.assertIs(status.state, RepoState.NO_REMOTE)

    def test_no_upstream(self) -> None:
        git(self.clone, "checkout", "-b", "sem-upstream")
        status = analyze_repo(self.clone, do_fetch=False)
        self.assertIs(status.state, RepoState.NO_UPSTREAM)

    def test_detached_head(self) -> None:
        head = git(self.clone, "rev-parse", "HEAD").stdout.strip()
        git(self.clone, "checkout", head)
        status = analyze_repo(self.clone, do_fetch=False)
        self.assertIs(status.state, RepoState.DETACHED)

    def test_conflict_in_progress(self) -> None:
        git_dir = self.clone / ".git"
        (git_dir / "MERGE_HEAD").write_text("0" * 40, encoding="utf-8")
        status = analyze_repo(self.clone, do_fetch=False)
        self.assertIs(status.state, RepoState.CONFLICT)

    def test_pull_ff_only_applies_remote_commit(self) -> None:
        other = self._second_clone()
        commit(other, "remoto.txt", "mudança de fora")
        git(other, "push")
        status = analyze_repo(self.clone)
        ok, _message = pull_ff_only(status)
        self.assertTrue(ok)
        self.assertTrue((self.clone / "remoto.txt").exists())
        self.assertIs(analyze_repo(self.clone).state, RepoState.UP_TO_DATE)

    def test_push_sends_local_commit(self) -> None:
        commit(self.clone, "novo.txt", "mudança local")
        status = analyze_repo(self.clone)
        ok, _message = push(status)
        self.assertTrue(ok)
        self.assertIs(analyze_repo(self.clone).state, RepoState.UP_TO_DATE)

    def test_pull_ff_only_refuses_diverged(self) -> None:
        other = self._second_clone()
        commit(other, "remoto.txt", "mudança de fora")
        git(other, "push")
        commit(self.clone, "local.txt", "mudança local")
        status = analyze_repo(self.clone)
        ok, _message = pull_ff_only(status)
        self.assertFalse(ok)  # --ff-only nunca cria merge
        self.assertTrue((self.clone / "local.txt").exists())  # nada perdido


if __name__ == "__main__":
    unittest.main()


class AutoCommitTests(unittest.TestCase):
    """Fluxo de commit automático: commit de tudo + pull --ff-only + push."""

    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="fetchall-autocommit-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.remote, self.clone = make_remote_and_clone(self.base)
        # Identidade local para o commit automático não depender do global.
        git(self.clone, "config", "user.name", "Teste")
        git(self.clone, "config", "user.email", "teste@example.com")
        git(self.clone, "config", "commit.gpgsign", "false")

    def test_message_is_structured_with_weekday_date_and_time(self) -> None:
        from datetime import datetime

        message = syncer.build_auto_commit_message(datetime(2026, 7, 5, 14, 30))
        self.assertEqual(
            message,
            "chore: commit automático do Fetch All — domingo, 05/07/2026 14:30",
        )

    def test_candidates_exclude_dirty_repos_behind_remote(self) -> None:
        dirty_ok = RepoStatus(Path("/a"), RepoState.DIRTY, behind=0)
        dirty_behind = RepoStatus(Path("/b"), RepoState.DIRTY, behind=2)
        diverged = RepoStatus(Path("/c"), RepoState.DIVERGED)
        plan = syncer.SyncPlan(problems=[dirty_ok, dirty_behind, diverged])
        self.assertEqual(plan.auto_commit_candidates, [dirty_ok])

    def test_commits_pulls_and_pushes_dirty_repo(self) -> None:
        (self.clone / "novo.txt").write_text("pendente", encoding="utf-8")
        status = analyze_repo(self.clone)
        self.assertIs(status.state, RepoState.DIRTY)

        results = syncer.execute_auto_commits([status], "chore: teste automático")
        self.assertEqual([r.action for r in results], ["commit", "pull", "push"])
        self.assertTrue(all(r.ok for r in results))
        self.assertIs(analyze_repo(self.clone).state, RepoState.UP_TO_DATE)

    def test_failed_commit_stops_that_repo_without_sync(self) -> None:
        # Repositório limpo: "git commit" falha (nada a commitar) e o fluxo para.
        status = analyze_repo(self.clone)
        results = syncer.execute_auto_commits([status], "chore: teste")
        self.assertEqual([r.action for r in results], ["commit"])
        self.assertFalse(results[0].ok)
