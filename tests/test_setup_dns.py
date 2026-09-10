import unittest
from unittest.mock import patch
from hermesaki.setup_dns import public_dns, lookup
from hermesaki.setup_services import records_for
from subprocess import CompletedProcess

class PublicDns(unittest.TestCase):
    settings={'domain':'example.com','server_ip':'8.8.8.8'}
    def test_all_records_must_resolve(self):
        records=records_for(self.settings)
        def answer(name,kind):
            r=next(r for r in records if r['name']==name and r['type']==kind)
            return [(str(r['priority'])+' ' if kind=='MX' else '')+r['content']]
        with patch('hermesaki.setup_dns.lookup',side_effect=answer):self.assertEqual(public_dns(self.settings)['state'],'passed')
        with patch('hermesaki.setup_dns.lookup',return_value=[]):self.assertEqual(public_dns(self.settings)['state'],'pending')
    def test_missing_tool_remains_pending(self):
        with patch('hermesaki.setup_dns.lookup',side_effect=FileNotFoundError):self.assertEqual(public_dns(self.settings)['state'],'pending')
    def test_txt_chunks_joined(self):
        with patch('hermesaki.setup_dns.subprocess.run',return_value=CompletedProcess([],0,'"v=spf1 " "-all"\n')):
            self.assertEqual(lookup('example.com','TXT'),['v=spf1 -all'])
