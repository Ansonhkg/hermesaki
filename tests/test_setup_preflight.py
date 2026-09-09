import unittest
from unittest.mock import patch,MagicMock
from hermesaki.setup_preflight import host_checks

class Preflight(unittest.TestCase):
    settings={'domain':'example.com','server_ip':'203.0.113.10','owner_email':'owner@example.com'}
    def test_missing_tools_and_blocked_smtp_are_actionable(self):
        with patch('hermesaki.setup_preflight.platform.system',return_value='Linux'), patch('hermesaki.setup_preflight.subprocess.run',side_effect=FileNotFoundError), patch('hermesaki.setup_preflight.socket.socket',side_effect=OSError), patch('hermesaki.setup_preflight.socket.create_connection',side_effect=TimeoutError), patch('hermesaki.setup_preflight.shutil.which',return_value=None):
            result=host_checks(self.settings)
        checks={x['id']:x for x in result['checks']}
        for name in ('docker','public_ip','smtp_bind','smtp_outbound'):
            self.assertEqual(checks[name]['state'],'blocked')
            self.assertTrue(checks[name]['remedy'])
        self.assertEqual(checks['reverse_dns']['state'],'pending')
        self.assertFalse(result['ready'])
        self.assertFalse(result['complete'])
    def test_successful_local_probes_never_claim_external_inbound(self):
        command=MagicMock(stdout='mail.example.com.\n')
        with patch('hermesaki.setup_preflight.platform.system',return_value='Linux'), patch('hermesaki.setup_preflight.subprocess.run',return_value=command), patch('hermesaki.setup_preflight.socket.socket'), patch('hermesaki.setup_preflight.socket.create_connection'), patch('hermesaki.setup_preflight.shutil.which',return_value='/usr/bin/dig'):
            result=host_checks(dict(self.settings,server_ip='8.8.8.8'))
        checks={x['id']:x for x in result['checks']}
        self.assertEqual(checks['smtp_outbound']['state'],'passed')
        self.assertEqual(checks['reverse_dns']['state'],'passed')
        self.assertEqual(checks['smtp_inbound']['state'],'pending')
        self.assertFalse(result['ready'])
