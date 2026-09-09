import json
import tempfile
import unittest
from pathlib import Path
from hermesaki.setup import Setup, Rejected
from hermesaki.setup_cloudflare import Cloudflare, CloudflareError


class Provider(Cloudflare):
    records=[]
    def all(self, path, query=None):
        if path == '/zones': return [{'id':'zone','name':'example.com','status':'active','account':{'id':'account'}}]
        if path.endswith('dns_records'): return list(self.records)
        return []


class Plans(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.setup=Setup(self.temp.name,Provider)
        self.owner='o'*64
        bootstrap=(Path(self.temp.name)/'bootstrap-token').read_text()
        self.setup.call('POST','/v1/setup/claim',bootstrap,{'owner_token':self.owner})
        self.settings={'domain':'example.com','server_ip':'203.0.113.10','owner_email':'owner@example.com'}
        self.setup.call('PUT','/v1/setup/configuration',self.owner,self.settings)

    def test_plan_saved_no_secret_exposed_or_unapproved_apply(self):
        secret='private-provider-credential-123456789'
        result=self.setup.call('PUT','/v1/setup/cloudflare',self.owner,{'token':secret})
        self.assertNotIn(secret,json.dumps(result))
        self.assertTrue(result['plan']['apply_available'])
        self.assertEqual(result['plan']['checks']['write_permissions'],'unverified')
        state=self.setup.call('GET','/v1/setup',self.owner,{})
        self.assertNotIn(secret,json.dumps(state))
        self.assertEqual(state['cloudflare_plan']['id'],result['plan']['id'])
        self.assertEqual((Path(self.temp.name)/'cloudflare-token').stat().st_mode & 0o777,0o600)
        with self.assertRaises(Rejected):self.setup.call('POST','/v1/setup/apply',self.owner,{'plan_id':result['plan']['id']})
        self.setup.call('PUT','/v1/setup/configuration',self.owner,dict(self.settings,owner_email='different@example.com'))
        self.assertIsNone(self.setup.call('GET','/v1/setup',self.owner,{})['cloudflare_plan'])

    def test_rejected_credential_does_not_replace_good_credential(self):
        self.setup.call('PUT','/v1/setup/cloudflare',self.owner,{'token':'good-credential-123456789'})
        class Denied:
            def __init__(self, token):pass
            def plan(self, settings):raise CloudflareError('cloudflare_permission_denied')
        self.setup.cloudflare=Denied
        with self.assertRaises(Rejected):self.setup.call('PUT','/v1/setup/cloudflare',self.owner,{'token':'bad-credential-123456789'})
        self.assertEqual((Path(self.temp.name)/'cloudflare-token').read_text(),'good-credential-123456789')

    def test_rotation_preserves_in_progress_plan(self):
        result=self.setup.call('PUT','/v1/setup/cloudflare',self.owner,{'token':'old-credential-123456789'})
        plan_id=result['plan']['id']
        with self.setup.connect() as db:
            db.execute('INSERT INTO progress VALUES(1,?)',(json.dumps({'plan_id':plan_id,'steps':{'tunnel':'created'},'state':'applying'}),))
        self.setup.call('PUT','/v1/setup/cloudflare',self.owner,{'token':'new-credential-123456789'})
        state=self.setup.call('GET','/v1/setup',self.owner,{})
        self.assertEqual(state['cloudflare_plan']['id'],plan_id)
        self.assertEqual(state['provisioning']['steps'],{'tunnel':'created'})
        self.assertEqual((Path(self.temp.name)/'cloudflare-token').read_text(),'new-credential-123456789')

    def test_existing_dns_conflict_never_overwritten(self):
        class Conflict(Provider):records=[{'name':'inbox.example.com','type':'A','content':'203.0.113.20'}]
        plan=Conflict('fixture').plan(self.settings)
        self.assertTrue(plan['conflicts'])
        self.assertFalse(plan['apply_available'])
        self.assertTrue(any(x['operation']=='conflict' for x in plan['actions']))

    def test_pagination_does_not_drop_second_page(self):
        class Pages(Cloudflare):
            def call(self, method,path,body=None,query=None):
                return {'result':list(range(50)) if query['page']==1 else [50], 'result_info':{'total_pages':2}}
        self.assertEqual(len(Pages('fixture').all('/zones')),51)

    def test_subdomain_finds_authorized_parent_zone(self):
        plan=Provider('fixture').plan(dict(self.settings,domain='trial.example.com'))
        self.assertEqual(plan['zone_id'],'zone')
        self.assertTrue(any(a.get('hostname')=='inbox.trial.example.com' for a in plan['actions']))

    def test_structured_next_actions_and_conflicts(self):
        state=self.setup.call('GET','/v1/setup',self.owner,{})
        self.assertEqual(state['next_action'],'connect_cloudflare')
        self.assertIn('smtp',state['missing_prerequisites'])
        self.setup.call('PUT','/v1/setup/cloudflare',self.owner,{'token':'credential-123456789012345'})
        state=self.setup.call('GET','/v1/setup',self.owner,{})
        self.assertEqual(state['state'],'plan_ready')
        self.assertEqual(state['operations'][-1]['path'],'/v1/setup/apply')
        self.assertFalse(state['complete'])
        class Conflict(Provider):records=[{'name':'inbox.example.com','type':'A','content':'203.0.113.20'}]
        self.setup.cloudflare=Conflict
        self.setup.call('POST','/v1/setup/plan',self.owner,{})
        state=self.setup.call('GET','/v1/setup',self.owner,{})
        self.assertEqual(state['state'],'blocked')
        self.assertTrue(state['validation_failures'])
