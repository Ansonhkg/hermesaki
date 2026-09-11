import base64
import os
import tempfile
import unittest
from pathlib import Path
from hermesaki.config import Config
from hermesaki.store import Store, Problem
from hermesaki.operator_configuration import read, plan, apply

class ConfigurationTests(unittest.TestCase):
    def test_review_apply_persistence_and_no_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory,'key').write_text(base64.b64encode(os.urandom(32)).decode())
            store=Store(directory);config=Config(state=directory)
            with self.assertRaises(Problem): apply(store,config,{'confirm_plan_id':'invented'})
            with self.assertRaises(Problem): plan(store,config,{'webmail_url':'javascript:alert(1)'})
            p=plan(store,config,{'webmail_url':'https://inbox.example.test/'})
            self.assertEqual(read(config)['webmail_url'],'')
            apply(store,config,{'confirm_plan_id':p['id']})
            self.assertEqual(read(Config(state=directory))['webmail_url'],'https://inbox.example.test/')
            with self.assertRaises(Problem): apply(store,config,{'confirm_plan_id':p['id']})
