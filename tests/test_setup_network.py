import unittest,time
from unittest.mock import patch,MagicMock
from hermesaki.setup_network import issue,probe,accept

class ExternalNetworkProbe(unittest.TestCase):
    def setUp(self):self.c=issue({'domain':'example.com','server_ip':'8.8.8.8'},'plan')
    def run_probe(self,source='1.1.1.1',banner=b'220 ready\r\n'):
        sock=MagicMock();sock.__enter__.return_value=sock;sock.getsockname.return_value=(source,1234);sock.recv.return_value=banner
        with patch('hermesaki.setup_network.socket.create_connection',return_value=sock),patch('hermesaki.setup_network.socket.gethostbyaddr',return_value=('mail.example.com',[],[])),patch('hermesaki.setup_network.socket.getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',25))]):return probe(self.c)
    def test_external_probe_passes(self):self.assertEqual(accept(self.c,self.run_probe(),'plan')['state'],'passed')
    def test_same_host_or_private_observer_cannot_pass(self):
        for source in ('8.8.8.8','127.0.0.1','192.168.1.2'):
            self.assertEqual(accept(self.c,self.run_probe(source),'plan')['state'],'pending')
    def test_blocked_smtp_pending_with_remedy(self):
        with patch('hermesaki.setup_network.socket.create_connection',side_effect=TimeoutError):r=probe(self.c)
        result=accept(self.c,r,'plan');self.assertEqual(result['state'],'pending');self.assertTrue(result['remedy'])
    def test_tampered_wrong_plan_and_expired_rejected(self):
        r=self.run_probe();r['observed']['source_ip']='9.9.9.9'
        with self.assertRaises(ValueError):accept(self.c,r,'plan')
        with self.assertRaises(ValueError):accept(self.c,self.run_probe(),'different')
        with self.assertRaises(ValueError):accept(self.c,self.run_probe(),'plan',self.c['expires_at']+1)

class NetworkApi(unittest.TestCase):
    def test_owner_scope_one_use_and_failed_receipt_persistence(self):
        import tempfile,secrets,json
        from pathlib import Path
        from hermesaki.setup import Setup,Rejected
        with tempfile.TemporaryDirectory() as directory:
            s=Setup(directory);owner=secrets.token_urlsafe(32)
            s.call('POST','/v1/setup/claim',Path(directory,'bootstrap-token').read_text(),{'owner_token':owner})
            s.call('PUT','/v1/setup/configuration',owner,{'domain':'example.com','server_ip':'8.8.8.8','owner_email':'owner@example.com'})
            with self.assertRaises(Rejected):s.call('POST','/v1/setup/network/challenge',owner,{})
            with s.connect() as db:db.execute('INSERT INTO deployment VALUES(1,?,?)',(json.dumps({'id':'test-plan'}),json.dumps({'state':'services_running'})))
            with self.assertRaises(Rejected):s.call('POST','/v1/setup/network/challenge','wrong',{})
            c=s.call('POST','/v1/setup/network/challenge',owner,{})
            with patch('hermesaki.setup_network.socket.create_connection',side_effect=TimeoutError):r=probe(c)
            result=s.call('POST','/v1/setup/network/result',owner,r);self.assertEqual(result['state'],'pending')
            with self.assertRaises(Rejected):s.call('POST','/v1/setup/network/result',owner,r)
            with s.connect() as db:
                self.assertEqual(s.network_result(db)['state'],'pending')
                self.assertIsNone(db.execute('SELECT challenge FROM network_probe').fetchone()['challenge'])
