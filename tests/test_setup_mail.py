import json
import time
import unittest
from unittest.mock import MagicMock
from hermesaki.setup_mail import receipt_results, start, verify

class ExternalMailVerification(unittest.TestCase):
    def setUp(self):
        self.session={'plan_id':'plan','sender':'hi@example.com','recipient':'test@external.test','subject':'Hermesaki setup verification fixture','message_id':'<fixture@example.com>','job_id':'job','started_at':int(time.time())}
        self.original='Message-ID: <fixture@example.com>\nFrom: hi@example.com\nTo: test@external.test\nSubject: Hermesaki setup verification fixture\nAuthentication-Results: mx.external.test; spf=pass; dkim=pass; dmarc=pass\n\nTest message'
    def test_matching_original_and_actual_reply_required(self):
        runtime=MagicMock()
        for reply,submitted in [(True,True),(False,True),(True,False)]:
            runtime.dc.return_value=json.dumps({'reply_received':reply,'outbound_submitted':submitted})
            self.assertEqual(verify(runtime,self.session,self.original)['state'],'passed' if reply and submitted else 'pending')
    def test_wrong_message_cannot_be_reused(self):
        for old,new in [('fixture@example.com','other@example.com'),('hi@example.com','other@example.com'),('test@external.test','other@external.test'),('verification fixture','verification other')]:
            with self.assertRaises(ValueError):receipt_results(self.session,self.original.replace(old,new))
    def test_body_and_split_authentication_headers_are_not_proof(self):
        for report in ['ARC-Authentication-Results: mx.external.test; spf=pass; dkim=pass; dmarc=pass','Authentication-Results: mx.external.test; spf=pass\nAuthentication-Results: other.test; dkim=pass; dmarc=pass','X-Other: ignored\n\nAuthentication-Results: mx.external.test; spf=pass; dkim=pass; dmarc=pass']:
            original=self.original.replace('Authentication-Results: mx.external.test; spf=pass; dkim=pass; dmarc=pass',report)
            self.assertFalse(receipt_results(self.session,original)['provider_report_passed'])
    def test_expired_test_cannot_pass(self):
        self.session['started_at']-=86401
        runtime=MagicMock()
        with self.assertRaises(ValueError):verify(runtime,self.session,self.original)
        runtime.dc.assert_not_called()
    def test_validation_before_send_and_safe_interpolation(self):
        runtime=MagicMock();plan={'id':'plan','first_mailbox':'hi@example.com'}
        for recipient in ['invalid','hi@example.com','a\n@elsewhere.test']:
            with self.assertRaises(ValueError):start(runtime,plan,recipient,'fixture')
        runtime.dc.assert_not_called()
        runtime.dc.return_value=json.dumps({'id':'job','message_id':'<id@example.com>'})
        start(runtime,plan,'SUBJECT@external.test','fixture')
        script=runtime.dc.call_args.kwargs['stdin']
        compile(script,'runtime','exec')
        self.assertIn("'SUBJECT@external.test'",script)
        self.assertIn('revoked=1',script)

class ExternalMailSetupApi(unittest.TestCase):
    def test_retry_validation_reset_and_original_not_stored(self):
        import tempfile,secrets
        from pathlib import Path
        from unittest.mock import patch
        from hermesaki.setup import Setup,Rejected
        with tempfile.TemporaryDirectory() as directory:
            setup=Setup(directory);owner=secrets.token_urlsafe(32)
            setup.call('POST','/v1/setup/claim',Path(directory,'bootstrap-token').read_text(),{'owner_token':owner})
            setup.call('PUT','/v1/setup/configuration',owner,{'domain':'example.com','server_ip':'8.8.8.8','owner_email':'hi@example.com'})
            path='/v1/setup/mail/start';payload={'confirm_recipient':'test@external.test'}
            with self.assertRaises(Rejected):setup.call('POST',path,owner,payload)
            with setup.connect() as db:db.execute('INSERT INTO deployment VALUES(1,?,?)',(json.dumps({'id':'plan','first_mailbox':'hi@example.com'}),json.dumps({'state':'services_running'})))
            with self.assertRaises(Rejected):setup.call('POST',path,'wrong',payload)
            with self.assertRaises(Rejected):setup.call('POST',path,owner,{'confirm_recipient':'invalid'})
            with setup.connect() as db:self.assertIsNone(db.execute('SELECT * FROM mail_verification').fetchone())
            session={'plan_id':'plan','recipient':'test@external.test'}
            with patch('hermesaki.setup.start_mail',return_value=session) as send:
                self.assertEqual(setup.call('POST',path,owner,payload),session)
                self.assertEqual(setup.call('POST',path,owner,payload),session)
                send.assert_called_once()
            result={'id':'external_mail','state':'pending'}
            with patch('hermesaki.setup.verify_mail',return_value=result):
                self.assertEqual(setup.call('POST','/v1/setup/mail/verify',owner,{'original':'private-original-content'}),result)
            self.assertNotIn(b'private-original-content',setup.database.read_bytes())
            with self.assertRaises(Rejected):setup.call('POST','/v1/setup/mail/reset',owner,{})
            setup.call('POST','/v1/setup/mail/reset',owner,{'confirm_new_test':True})
            with setup.connect() as db:self.assertIsNone(db.execute('SELECT * FROM mail_verification').fetchone())
