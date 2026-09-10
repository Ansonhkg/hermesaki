import unittest
from hermesaki.setup_handover import handover, REQUIRED

class HandoverGate(unittest.TestCase):
    def proof(self):return {'checks':[{'id':k,'state':'passed'} for k in REQUIRED], 'checked_at':1000}
    def finish(self,p):return handover(p,{'domain':'example.com'},'plan',1001)
    def test_all_required_checks_pass_and_result_has_no_credentials(self):
        result=self.finish(self.proof());self.assertTrue(result['complete']);self.assertTrue(result['setup_mutations_retired'])
        self.assertEqual(result['operator_url'],'https://hermesaki.example.com')
        self.assertNotIn('token',result);self.assertNotIn('password',result)
    def test_ready_boolean_cannot_replace_missing_checks(self):
        with self.assertRaises(ValueError):self.finish({'ready':True,'checks':[],'checked_at':1000})
    def test_every_pending_or_failed_check_blocks_completion(self):
        for state in ('pending','failed','blocked'):
            for i in range(len(REQUIRED)):
                p=self.proof();p['checks'][i]['state']=state
                with self.assertRaises(ValueError):self.finish(p)
    def test_stale_and_future_proof_rejected(self):
        for stamp in (0,1500):
            p=self.proof();p['checked_at']=stamp
            with self.assertRaises(ValueError):self.finish(p)
    def test_duplicates_rejected(self):
        p=self.proof();p['checks'].append(p['checks'][0])
        with self.assertRaises(ValueError):self.finish(p)

class HandoverApi(unittest.TestCase):
    def test_live_recheck_and_retired_mutations(self):
        import json,secrets,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from hermesaki.setup import Setup,Rejected
        with tempfile.TemporaryDirectory() as directory:
            app=Setup(directory);owner=secrets.token_urlsafe(32)
            app.call('POST','/v1/setup/claim',Path(directory,'bootstrap-token').read_text(),{'owner_token':owner})
            app.call('PUT','/v1/setup/configuration',owner,{'domain':'example.com','server_ip':'8.8.8.8','owner_email':'owner@example.com'})
            with app.connect() as db:
                db.execute('INSERT INTO deployment VALUES(1,?,?)',(json.dumps({'id':'plan'}),json.dumps({'state':'services_running'})))
            for token,payload in [('',{'confirm_plan_id':'plan'}),(owner,{'confirm_plan_id':'wrong'}),(owner,{'confirm_plan_id':'plan','ready':True})]:
                with self.assertRaises(Rejected):app.call('POST','/v1/setup/complete',token,payload)
            proof={'checks':[{'id':k,'state':'passed'} for k in REQUIRED],'checked_at':int(__import__('time').time())}
            pending={**proof,'checks':[{'id':k,'state':'pending'} for k in REQUIRED]}
            with patch('hermesaki.setup.verify_services',return_value=pending) as verify:
                with self.assertRaises(Rejected):app.call('POST','/v1/setup/complete',owner,{'confirm_plan_id':'plan'})
                verify.assert_called_once()
            with patch('hermesaki.setup.verify_services',return_value=proof) as verify:
                result=app.call('POST','/v1/setup/complete',owner,{'confirm_plan_id':'plan'})
                self.assertTrue(result['complete']);verify.assert_called_once()
            restarted=Setup(directory)
            self.assertTrue(restarted.call('GET','/v1/setup',owner,{})['complete'])
            with self.assertRaises(Rejected):restarted.call('POST','/v1/setup/services/apply',owner,{'confirm_plan_id':'plan'})
            self.assertFalse(Path(directory,'bootstrap-token').exists())
