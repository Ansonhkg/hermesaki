import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

spec=importlib.util.spec_from_file_location('reinstall',Path(__file__).parents[1]/'scripts/reinstall.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class ReinstallRestore(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.key=self.root/'key';self.key.write_bytes(os.urandom(32))
        self.archive=self.root/'backup';self.destination=self.root/'new'
    def archive_data(self,name='.runtime/mail-data/message',volume='/old/.runtime/mail-data:/var/lib/stalwart'):
        buf=io.BytesIO()
        with tarfile.open(fileobj=buf,mode='w:gz') as tar:
            member=tarfile.TarInfo(name);member.size=4;member.mode=0o600
            tar.addfile(member,io.BytesIO(b'mail'))
        nonce=os.urandom(12);self.archive.write_bytes(nonce+AESGCM(self.key.read_bytes()).encrypt(nonce,buf.getvalue(),r.AAD))
        self.archive.with_suffix('.compose.json').write_text(json.dumps({'services':{'mail':{'volumes':[volume]}}}))
    def test_restores_bytes_private_modes_and_new_mount(self):
        self.archive_data();path=r.restore(self.archive,self.key,self.destination,Path('/old'))
        f=self.destination/'.runtime/mail-data/message';self.assertEqual(f.read_bytes(),b'mail');self.assertEqual(f.stat().st_mode&0o777,0o600)
        self.assertTrue(json.loads(path.read_text())['services']['mail']['volumes'][0].startswith(str(self.destination)))
    def test_never_overwrites_existing_data(self):
        self.archive_data();self.destination.mkdir();(self.destination/'keep').write_text('original')
        with self.assertRaises(ValueError):r.restore(self.archive,self.key,self.destination,Path('/old'))
        self.assertEqual((self.destination/'keep').read_text(),'original')
    def test_path_traversal_rejected(self):
        self.archive_data('../escape')
        with self.assertRaises(ValueError):r.restore(self.archive,self.key,self.destination,Path('/old'))
        self.assertFalse(self.destination.exists())
    def test_tampered_archive_rejected_before_restore(self):
        self.archive_data();self.archive.write_bytes(self.archive.read_bytes()[:-1]+b'x')
        with self.assertRaises(Exception):r.restore(self.archive,self.key,self.destination,Path('/old'))
        self.assertFalse(self.destination.exists())
