import importlib.util
import secrets
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "backup", Path(__file__).resolve().parents[1] / "scripts/backup.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Backup(unittest.TestCase):
    def test_roundtrip_and_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "source"
            src.mkdir()
            (src / "secret").write_text("mail and keys")
            key = secrets.token_bytes(32)
            blob = m.pack(src, key)
            self.assertNotIn(b"mail and keys", blob)
            m.unpack(blob, key, root / "restored")
            self.assertEqual(
                "mail and keys", (root / "restored/state/secret").read_text()
            )
            with self.assertRaises(ValueError):
                m.unpack(blob, key, root / "restored")
            with self.assertRaises(Exception):
                m.unpack(blob, secrets.token_bytes(32), root / "wrong")
