import json
import unittest
from unittest.mock import MagicMock, patch
from hermesaki.setup_agent import verify
from hermesaki.setup_services import DeploymentError

class AgentVerification(unittest.TestCase):
    def run_check(self, responses, cleanup_error=False):
        runtime=MagicMock()
        issued={'inbox_id':'fixture-inbox','id':'fixture-token','token':'secret-mailbox-token'}
        runtime.dc.side_effect=[json.dumps(issued),DeploymentError('unavailable') if cleanup_error else '']
        opener=MagicMock()
        def response(code,value):
            r=MagicMock();r.__enter__.return_value=r;r.code=code;r.read.return_value=value if isinstance(value,bytes) else json.dumps(value).encode();return r
        opener.open.side_effect=[response(*r) for r in responses]
        with patch('hermesaki.setup_agent.urllib.request.build_opener',return_value=opener):
            result=verify(runtime,{'domain':'example.com'},{'id':'plan','first_mailbox':'hi@example.com'},{'client_id':'fixture-client','client_secret':'fixture-secret'})
        self.assertNotIn('secret',json.dumps(result))
        self.assertIn('revoked=1',runtime.dc.call_args.kwargs['stdin'])
        return result,opener
    def test_real_protocol_success_and_cleanup(self):
        result,opener=self.run_check([(200,{'result':{'content':[],'isError':False}}),(200,{'error':{'message':'scope_denied'}}),(401,{})])
        self.assertEqual(result['state'],'passed')
        calls=opener.open.call_args_list
        self.assertEqual(calls[0].args[0].get_header('User-agent'),'Hermesaki/0.1')
        self.assertEqual(json.loads(calls[1].args[0].data)['params']['arguments']['to'],[])
    def test_edge_html_and_http_200_errors_cannot_pass(self):
        for first in [(403,b'error code: 1010'),(200,{'error':{'message':'denied'}}),(302,b'login')]:
            result,_=self.run_check([first,(200,{'error':{'message':'scope_denied'}}),(401,{})]);self.assertEqual(result['state'],'pending')
    def test_missing_denial_or_failed_cleanup_cannot_pass(self):
        good=[(200,{'result':{'isError':False}}),(200,{'error':{'message':'scope_denied'}}),(401,{})]
        result,_=self.run_check(good,True);self.assertEqual(result['state'],'pending')
        good[1]=(200,{'result':{}})
        result,_=self.run_check(good);self.assertEqual(result['state'],'pending')
    def test_credentials_validated_before_runtime(self):
        runtime=MagicMock()
        with self.assertRaises(ValueError):verify(runtime,{}, {}, {'client_id':'bad'})
        runtime.dc.assert_not_called()

class AgentSetupApi(unittest.TestCase):
    def test_auth_deployment_guard_and_no_credential_storage(self):
        import tempfile,secrets
        from pathlib import Path
        from hermesaki.setup import Setup,Rejected
        with tempfile.TemporaryDirectory() as directory:
            setup=Setup(directory);owner=secrets.token_urlsafe(32)
            setup.call('POST','/v1/setup/claim',Path(directory,'bootstrap-token').read_text(),{'owner_token':owner})
            setup.call('PUT','/v1/setup/configuration',owner,{'domain':'example.com','server_ip':'8.8.8.8','owner_email':'hi@example.com'})
            credentials={'client_id':'private-test-client','client_secret':'private-test-secret'}
            for credential in ('wrong',owner):
                with self.assertRaises(Rejected):setup.call('POST','/v1/setup/agent/verify',credential,credentials)
            with setup.connect() as db:db.execute('INSERT INTO deployment VALUES(1,?,?)',(json.dumps({'id':'plan','first_mailbox':'hi@example.com'}),json.dumps({'state':'services_running'})))
            observed={'id':'authenticated_agent','state':'pending','plan_id':'plan','checked_at':1,'detail':'Denied'}
            with patch('hermesaki.setup.verify_agent',return_value=observed):
                self.assertEqual(setup.call('POST','/v1/setup/agent/verify',owner,credentials),observed)
            with setup.connect() as db:self.assertEqual(setup.agent_result(db),observed)
            self.assertNotIn(b'private-test-secret',setup.database.read_bytes())
