import json
import tempfile
import unittest
from pathlib import Path
from hermesaki.setup_services import Services, DeploymentError
from hermesaki.setup_runtime import Runtime

class RuntimeSafety(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.services=Services(self.temp.name);self.runtime=Runtime(self.services)
        self.settings={'domain':'isolated.example.com','server_ip':'203.0.113.10','owner_email':'owner@example.com'}
    def test_compose_exposes_only_smtp_and_does_not_share_existing_storage(self):
        config=self.runtime.compose(self.settings)
        for name,service in config['services'].items():
            self.assertEqual(service.get('ports',[]),[{'target':25,'published':'25','host_ip':'203.0.113.10'}] if name=='mail' else [])
            self.assertEqual(service['restart'],'unless-stopped')
        self.assertTrue(config['networks']['private']['internal'])
        self.assertTrue(config['name'].startswith('hermesaki-fresh-'))
        self.assertNotIn('/opt/',json.dumps(config))
    def test_subprocess_failure_is_redacted(self):
        with self.assertRaises(DeploymentError) as error:
            self.runtime.run(['python3','-c',"import sys;sys.stderr.write('SECRET');sys.exit(1)"])
        self.assertNotIn('SECRET',str(error.exception))
    def test_existing_owned_plan_mismatch_never_overwrites(self):
        self.services.root.mkdir();(self.services.root/'owned-plan').write_text('old')
        with self.assertRaises(DeploymentError):
            self.runtime.prepare(self.settings,{'id':'new'},None)
        self.assertEqual((self.services.root/'owned-plan').read_text(),'old')
