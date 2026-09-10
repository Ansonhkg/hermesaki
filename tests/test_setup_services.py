import tempfile
import unittest
from pathlib import Path
from hermesaki.setup_services import Services, DeploymentError, records_for, dns_plan

class Provider:
    def __init__(self):self.records=[];self.writes=0
    def all(self,path,query):return [r for r in self.records if r['name']==query['name']]
    def call(self,method,path,record):self.records.append(dict(record));self.writes+=1
    def plan(self,settings):return {'conflicts':[],'actions':[{'operation':'reuse'}]}

class ServicePlans(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.services=Services(self.temp.name)
        self.provider=Provider()
        self.settings={'domain':'trial.example.com','server_ip':'203.0.113.10','owner_email':'owner@example.com'}
        self.options={'access_team':'example-team','first_mailbox':'hi@trial.example.com','accept_acme_terms':True}
    def plan(self):
        return self.services.plan(self.provider,self.settings,{'zone_id':'zone','account_id':'account'}, {'state':'web_resources_applied','tunnel_id':'tunnel'},self.options)
    def test_plan_contains_mail_dns_services_auth_and_no_public_http(self):
        plan=self.plan()
        self.assertEqual({a['record']['type'] for a in plan['actions']},{'A','MX','TXT'})
        self.assertFalse(plan['actions'][0]['record']['proxied'])
        self.assertEqual(plan['services']['api']['published_ports'],[])
        self.assertEqual(plan['id'],self.plan()['id'])
        self.assertEqual(self.provider.writes,0)
    def test_existing_mail_and_unowned_data_block(self):
        self.provider.records=[{'type':'MX','name':self.settings['domain'],'content':'other.example.com','priority':10}]
        self.assertFalse(self.plan()['apply_available'])
        self.services.root.mkdir();(self.services.root/'mail').touch()
        self.assertIn('not owned',self.plan()['conflicts'][-1])
    def test_retry_reconciles_lost_dns_response_and_preserves_unrelated_txt(self):
        self.provider.records=[{'type':'TXT','name':self.settings['domain'],'content':'site-verification=keep'}]
        plan=self.plan(); progress={}
        self.services.apply_dns(self.provider,plan,progress,lambda p:None)
        self.services.apply_dns(self.provider,plan,progress,lambda p:None)
        self.assertEqual(self.provider.writes,4)
        self.assertEqual(len(self.provider.records),5)
        progress['dns_inflight']=['A:mail.trial.example.com']
        self.services.apply_dns(self.provider,plan,progress,lambda p:None)
        self.assertEqual(progress['dns_inflight'],[])
    def test_unresolved_write_does_not_repeat(self):
        plan=self.plan()
        with self.assertRaises(DeploymentError):
            self.services.apply_dns(self.provider,plan,{'dns_inflight':['A:mail.trial.example.com']},lambda p:None)
        self.assertEqual(self.provider.writes,0)
    def test_ipv6_and_conflicting_cname(self):
        records=records_for(dict(self.settings,server_ip='2001:db8::1'))
        self.assertEqual(records[0]['type'],'AAAA')
        self.provider.records=[{'type':'CNAME','name':records[0]['name'],'content':'other.example.com'}]
        self.assertTrue(dns_plan(self.provider,'zone',records)[1])
    def test_plan_requires_terms_and_domain_scoped_mailbox(self):
        for changes in ({'accept_acme_terms':False},{'first_mailbox':'hi@other.example.com'},{'access_team':'https://example.com'}):
            self.options.update(changes)
            with self.assertRaises(DeploymentError):self.plan()
            self.options={'access_team':'example-team','first_mailbox':'hi@trial.example.com','accept_acme_terms':True}

class ServiceAuthorization(unittest.TestCase):
    def test_service_apply_requires_owner_exact_plan_and_current_dns(self):
        import json
        from hermesaki.setup import Setup, Rejected
        from test_setup_apply import Fixture
        with tempfile.TemporaryDirectory() as directory:
            provider=Fixture();setup=Setup(directory,lambda token:provider);owner='o'*64
            setup.call('POST','/v1/setup/claim',(Path(directory)/'bootstrap-token').read_text(),{'owner_token':owner})
            settings={'domain':'example.com','server_ip':'203.0.113.10','owner_email':'owner@example.com'}
            setup.call('PUT','/v1/setup/configuration',owner,settings)
            web=setup.call('PUT','/v1/setup/cloudflare',owner,{'token':'fixture-long-credential-123'})['plan']
            setup.call('POST','/v1/setup/apply',owner,{'confirm_plan_id':web['id']})
            plan=setup.call('POST','/v1/setup/services/plan',owner,{'access_team':'fixture','first_mailbox':'hi@example.com','accept_acme_terms':True})
            for token,data in [('',{'confirm_plan_id':plan['id']}),(owner,{}),(owner,{'confirm_plan_id':'stale'})]:
                with self.assertRaises(Rejected):setup.call('POST','/v1/setup/services/apply',token,data)
            self.assertFalse((Path(directory)/'installation').exists())
            provider.records.append({'type':'MX','name':'example.com','content':'another.example.com','priority':10})
            with self.assertRaises(Rejected) as error:setup.call('POST','/v1/setup/services/apply',owner,{'confirm_plan_id':plan['id']})
            self.assertEqual(error.exception.code,'service_plan_changed_review_again')
            self.assertFalse((Path(directory)/'installation').exists())
            with self.assertRaises(Rejected):setup.call('POST','/v1/setup/services/credentials',owner,{})

class OutgoingAddress(unittest.TestCase):
    def test_separate_egress_is_in_spf_but_does_not_change_inbound_record(self):
        from hermesaki.setup_services import records_for
        from hermesaki.setup import validate,Rejected
        settings=validate({'domain':'example.com','server_ip':'2606:4700::1111','owner_email':'hi@example.com','outbound_ip':'1.1.1.1'})
        records=records_for(settings)
        self.assertEqual(records[0]['type'],'AAAA')
        self.assertEqual(records[0]['content'],'2606:4700::1111')
        self.assertEqual(records[2]['content'],'v=spf1 ip6:2606:4700::1111 ip4:1.1.1.1 -all')
        with self.assertRaises(Rejected):validate(dict(settings,outbound_ip='127.0.0.1'))
        self.assertNotIn('outbound_ip',validate(dict(settings,outbound_ip='')))
