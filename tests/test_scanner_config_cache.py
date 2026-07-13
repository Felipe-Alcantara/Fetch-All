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
from fetchall import scanner as scanner_module
from fetchall.scanner import (
    darwin_cloudstorage_paths,
    find_git_repos,
    local_mount_points,
    mount_skip_paths,
    parse_bsd_mount_skips,
    parse_linux_mount_skips,
    resolve_scan_roots,
)


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

    def test_multiple_roots_scanned_in_parallel_find_everything(self) -> None:
        # Com mais de uma raiz, cada uma é varrida em thread própria;
        # o resultado precisa ser o mesmo da varredura sequencial.
        _fake_repo(self.base / "disco-a" / "projeto-a")
        _fake_repo(self.base / "disco-b" / "projeto-b")
        _fake_repo(self.base / "disco-b" / "pasta" / "projeto-c")
        found = sorted(
            p.name for p in find_git_repos(
                [str(self.base / "disco-a"), str(self.base / "disco-b")], []
            )
        )
        self.assertEqual(found, ["projeto-a", "projeto-b", "projeto-c"])

    def test_repeated_roots_do_not_duplicate_repos(self) -> None:
        _fake_repo(self.base / "projeto")
        found = list(find_git_repos([str(self.base), str(self.base)], []))
        self.assertEqual(len(found), 1)

    def test_nested_roots_are_split_between_threads_without_duplicates(self) -> None:
        # Simula "/" e um disco montado dentro dele (ex.: /mnt/dados):
        # a raiz-mãe não desce na raiz aninhada, que tem thread própria.
        _fake_repo(self.base / "projeto-raiz")
        _fake_repo(self.base / "montado" / "projeto-disco")
        found = sorted(
            p.name for p in find_git_repos(
                [str(self.base), str(self.base / "montado")], []
            )
        )
        self.assertEqual(found, ["projeto-disco", "projeto-raiz"])

    def test_skip_paths_prune_mount_points(self) -> None:
        # Simula uma montagem virtual/de rede dentro da árvore varrida.
        _fake_repo(self.base / "projeto")
        _fake_repo(self.base / "montagem-de-rede" / "repo-remoto")
        found = list(
            find_git_repos(
                [str(self.base)], [],
                skip_paths={str(self.base / "montagem-de-rede")},
            )
        )
        self.assertEqual([p.name for p in found], ["projeto"])


class MountParsingTests(unittest.TestCase):
    def test_linux_mounts_skip_virtual_and_network(self) -> None:
        lines = [
            "/dev/sda2 / ext4 rw,relatime 0 0",
            "proc /proc proc rw,nosuid 0 0",
            "sysfs /sys sysfs rw,nosuid 0 0",
            "tmpfs /run tmpfs rw,nosuid 0 0",
            "/dev/sdb1 /mnt/dados fuseblk rw,relatime 0 0",  # ntfs-3g: local
            "servidor:/dados /mnt/nas nfs4 rw,relatime 0 0",
            "//servidor/share /mnt/smb cifs rw,relatime 0 0",
            "user@host: /mnt/ssh fuse.sshfs rw,nosuid 0 0",
            "/var/lib/snapd/snaps/x.snap /snap/x/1 squashfs ro 0 0",
            "cgroup2 /sys/fs/cgroup cgroup2 rw,nosuid 0 0",
        ]
        skips = parse_linux_mount_skips(lines)
        self.assertIn("/proc", skips)
        self.assertIn("/sys", skips)
        self.assertIn("/run", skips)
        self.assertIn("/mnt/nas", skips)
        self.assertIn("/mnt/smb", skips)
        self.assertIn("/mnt/ssh", skips)
        self.assertIn("/snap/x/1", skips)
        self.assertNotIn("/", skips)  # raiz é disco local
        self.assertNotIn("/mnt/dados", skips)  # fuseblk (ntfs-3g) é local

    def test_linux_mounts_decode_octal_escaped_spaces(self) -> None:
        lines = [r"tmpfs /mnt/pasta\040com\040espaço tmpfs rw 0 0"]
        self.assertEqual(
            parse_linux_mount_skips(lines), {"/mnt/pasta com espaço"}
        )

    def test_bsd_mount_output_skip_virtual(self) -> None:
        lines = [
            "/dev/disk3s1s1 on / (apfs, sealed, local, read-only journaled)",
            "devfs on /dev (devfs, local, nobrowse)",
            "map auto_home on /System/Volumes/Data/home (autofs, automounted)",
            "//user@server/share on /Volumes/share (smbfs, nodev, nosuid)",
            "/dev/disk4s1 on /Volumes/Backup (apfs, local, journaled)",
        ]
        skips = parse_bsd_mount_skips(lines)
        self.assertEqual(
            skips, {"/dev", "/System/Volumes/Data/home", "/Volumes/share"}
        )

    def test_local_mount_points_one_root_per_local_disk(self) -> None:
        mounts = [
            ("/", "ext4"),
            ("/home", "ext4"),               # partição própria: raiz paralela
            ("/mnt/win", "fuseblk"),         # ntfs-3g: disco local
            ("/boot/efi", "vfat"),           # sistema: fora
            ("/mnt/nas", "nfs4"),            # rede: fora
            ("/proc", "proc"),               # virtual: fora
            ("/media/felipe/pen", "exfat"),  # removível: raiz paralela
        ]
        self.assertEqual(
            local_mount_points(mounts),
            ["/", "/home", "/media/felipe/pen", "/mnt/win"],
        )

    def test_local_mount_points_on_macos_skip_system_volumes(self) -> None:
        mounts = [
            ("/", "apfs"),
            ("/System/Volumes/Data", "apfs"),  # firmlink: duplicaria "/"
            ("/Volumes/Backup", "apfs"),
        ]
        with mock.patch.object(scanner_module.sys, "platform", "darwin"):
            self.assertEqual(
                local_mount_points(mounts), ["/", "/Volumes/Backup"]
            )

    def test_local_mount_points_fall_back_to_root(self) -> None:
        self.assertEqual(local_mount_points([]), ["/"])

    def test_macos_skips_system_volumes_during_walk(self) -> None:
        # Varrer "/" no macOS descia em /System/Volumes/Data e revarria o
        # volume inteiro — inclusive os discos externos, que reaparecem em
        # /System/Volumes/Data/Volumes/… e escapam da poda de raízes aninhadas.
        mounts = [("/", "apfs"), ("/System/Volumes/Data", "apfs"), ("/dev", "devfs")]
        with (
            mock.patch.object(scanner_module.sys, "platform", "darwin"),
            mock.patch.object(scanner_module, "_list_mounts", return_value=mounts),
            mock.patch.object(
                scanner_module,
                "darwin_cloudstorage_paths",
                return_value={"/Users/ana/Library/CloudStorage"},
            ),
        ):
            self.assertEqual(
                mount_skip_paths(),
                {"/dev", "/System/Volumes", "/Users/ana/Library/CloudStorage"},
            )

    def test_linux_does_not_skip_system_volumes(self) -> None:
        mounts = [("/", "ext4"), ("/proc", "proc")]
        with (
            mock.patch.object(scanner_module.sys, "platform", "linux"),
            mock.patch.object(scanner_module, "_list_mounts", return_value=mounts),
        ):
            self.assertEqual(mount_skip_paths(), {"/proc"})

    def test_darwin_cloudstorage_paths_only_where_folder_exists(self) -> None:
        # A poda de drives de nuvem é por caminho exato (~/Library/CloudStorage
        # de cada usuário), não por nome de pasta — um projeto chamado
        # "CloudStorage" em outro lugar continua sendo varrido.
        users = Path(tempfile.mkdtemp(prefix="fetchall-users-"))
        self.addCleanup(shutil.rmtree, users, ignore_errors=True)
        (users / "ana" / "Library" / "CloudStorage").mkdir(parents=True)
        (users / "bia" / "Library").mkdir(parents=True)  # sem CloudStorage
        (users / "Shared").mkdir()
        self.assertEqual(
            darwin_cloudstorage_paths(str(users)),
            {str(users / "ana" / "Library" / "CloudStorage")},
        )

    def test_darwin_cloudstorage_paths_missing_users_root(self) -> None:
        self.assertEqual(darwin_cloudstorage_paths("/nao-existe"), set())


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
