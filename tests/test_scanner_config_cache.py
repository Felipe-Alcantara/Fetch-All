"""Testes da varredura, da configuração e do cache de varredura."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fetchall import cache as cache_module
from fetchall import config as config_module
from fetchall.cache import load_cache, save_cache
from fetchall.config import DEFAULT_EXCLUDES, Config, load_config, save_config
from fetchall.scanner import find_git_repos, resolve_scan_roots


def _fake_repo(path: Path) -> None:
    """Cria a estrutura mínima que o scanner reconhece como repositório."""
    (path / ".git").mkdir(parents=True)


class ScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="fetchall-scan-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def test_finds_repos_including_nested(self) -> None:
        _fake_repo(self.base / "projeto-a")
        _fake_repo(self.base / "pasta" / "projeto-b")
        _fake_repo(self.base / "projeto-a" / "submodulo")
        found = sorted(find_git_repos([str(self.base)], []))
        self.assertEqual(len(found), 3)

    def test_prunes_excluded_dirs_case_insensitive(self) -> None:
        _fake_repo(self.base / "node_modules" / "lib")
        _fake_repo(self.base / "SteamLibrary" / "jogo")
        _fake_repo(self.base / "projeto")
        found = list(find_git_repos([str(self.base)], ["node_modules", "steamlibrary"]))
        self.assertEqual([p.name for p in found], ["projeto"])

    def test_does_not_descend_into_git_dir(self) -> None:
        _fake_repo(self.base / "projeto")
        # Um ".git" interno (ex.: de template copiado) não deve virar repositório.
        (self.base / "projeto" / ".git" / "modules" / "x" / ".git").mkdir(parents=True)
        found = list(find_git_repos([str(self.base)], []))
        self.assertEqual(len(found), 1)

    def test_missing_root_is_ignored(self) -> None:
        found = list(find_git_repos([str(self.base / "nao-existe")], []))
        self.assertEqual(found, [])

    def test_resolve_scan_roots_prefers_configured(self) -> None:
        self.assertEqual(resolve_scan_roots(["X:\\dado"]), ["X:\\dado"])

    def test_resolve_scan_roots_falls_back_to_drives(self) -> None:
        roots = resolve_scan_roots([])
        self.assertTrue(roots)  # sempre há pelo menos um disco/raiz


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="fetchall-cfg-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        patcher = mock.patch.object(
            config_module, "CONFIG_PATH", self.base / "config.json"
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_when_missing(self) -> None:
        config = load_config()
        self.assertEqual(config.scan_roots, [])
        self.assertIn("node_modules", config.exclude_dirs)

    def test_roundtrip_preserves_values(self) -> None:
        save_config(Config(scan_roots=["C:\\Projetos"], max_workers=4))
        config = load_config()
        self.assertEqual(config.scan_roots, ["C:\\Projetos"])
        self.assertEqual(config.max_workers, 4)

    def test_new_default_excludes_merged_into_old_config(self) -> None:
        # Config antigo, salvo antes de exclusões novas existirem.
        config_module.CONFIG_PATH.write_text(
            '{"scan_roots": [], "exclude_dirs": ["minha-pasta"]}', encoding="utf-8"
        )
        config = load_config()
        self.assertIn("minha-pasta", config.exclude_dirs)  # escolha do usuário fica
        for name in DEFAULT_EXCLUDES:
            self.assertIn(name, config.exclude_dirs)  # padrões novos entram

    def test_invalid_json_raises_clear_error(self) -> None:
        config_module.CONFIG_PATH.write_text("{quebrado", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_config()


class CacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="fetchall-cache-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        patcher = mock.patch.object(
            cache_module, "CACHE_PATH", self.base / "scan_cache.json"
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_roundtrip_and_root_matching(self) -> None:
        repo = self.base / "repo"
        _fake_repo(repo)
        save_cache(["C:\\", "D:\\"], [repo])
        cache = load_cache()
        self.assertIsNotNone(cache)
        self.assertTrue(cache.matches_roots(["D:\\", "C:\\"]))  # ordem não importa
        self.assertFalse(cache.matches_roots(["C:\\"]))
        self.assertEqual(cache.valid_repos(), [repo])

    def test_deleted_repos_are_dropped(self) -> None:
        repo = self.base / "apagado"
        _fake_repo(repo)
        save_cache(["C:\\"], [repo])
        shutil.rmtree(repo)
        self.assertEqual(load_cache().valid_repos(), [])

    def test_corrupted_cache_is_treated_as_missing(self) -> None:
        cache_module.CACHE_PATH.write_text("{quebrado", encoding="utf-8")
        self.assertIsNone(load_cache())


if __name__ == "__main__":
    unittest.main()
