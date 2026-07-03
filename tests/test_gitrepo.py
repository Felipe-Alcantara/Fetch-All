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

from fetchall.gitrepo import RepoState, analyze_repo, pull_ff_only, push
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
