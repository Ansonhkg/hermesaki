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

    def test_acme_certificate_links_survive_restore(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'source';(src/'acme/archive').mkdir(parents=True);(src/'acme/live').mkdir()
            (src/'acme/archive/cert1.pem').write_text('fixture-certificate')
            (src/'acme/live/fullchain.pem').symlink_to('../archive/cert1.pem')
            key=secrets.token_bytes(32);m.unpack(m.pack(src,key),key,root/'restore')
            restored=root/'restore/state/acme/live/fullchain.pem'
            self.assertTrue(restored.is_symlink());self.assertEqual(restored.read_text(),'fixture-certificate')

    def test_links_cannot_escape_restored_state(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'source';src.mkdir();(root/'outside').write_text('outside')
            (src/'escape').symlink_to('../../outside')
            key=secrets.token_bytes(32)
            with self.assertRaises(ValueError):m.unpack(m.pack(src,key),key,root/'restore')
            self.assertEqual((root/'outside').read_text(),'outside')
