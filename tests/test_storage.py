"""Testes da persistência atômica compartilhada por configuração e cache."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fetchall.storage import atomic_write_text


class AtomicWriteTests(unittest.TestCase):
    def test_failed_write_removes_temporary_file_and_preserves_target(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="fetchall-storage-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        target = base / "config.json"
        target.write_text("anterior", encoding="utf-8")

        with (
            mock.patch("fetchall.storage.os.fsync", side_effect=OSError("disco cheio")),
            self.assertRaises(OSError),
        ):
            atomic_write_text(target, "novo")

        self.assertEqual(target.read_text(encoding="utf-8"), "anterior")
        self.assertEqual(list(base.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
