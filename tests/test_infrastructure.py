import base64
import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from hermesaki.config import Config
from hermesaki.store import Store, Problem
from hermesaki import infrastructure as infra

class Provider:
    def __init__(self):
        self.record={'type':'A','name':'mail.example.test','content':'192.0.2.1','ttl':300,'proxied':False}
        self.writes=0
        self.lose=False
    def all(self,path,query=None):
        return [{'id':'zone','status':'active','account':{'id':'account'}}]
    def call(self,method,path,body=None):
        if method=='PUT':
            self.writes+=1;self.record=copy.deepcopy(body)
            if self.lose: raise infra.CloudflareError('lost_response')
        return {'result':copy.deepcopy(self.record)}

class InfrastructureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        Path(self.tmp.name,'key').write_text(base64.b64encode(os.urandom(32)).decode())
        self.store=Store(self.tmp.name);self.config=Config(state=self.tmp.name)
        self.cf=Provider();self.patcher=patch.object(infra,'provider',return_value=self.cf);self.patcher.start();self.addCleanup(self.patcher.stop)
    def plan(self):return infra.plan(self.store,self.config,{'kind':'dns','id':'record','change':{'ttl':600}})
    def test_review_required_and_stale_changes_rejected(self):
        p=self.plan();self.assertEqual(self.cf.writes,0)
        with self.assertRaises(Problem):infra.apply(self.store,self.config,{'confirm_plan_id':'wrong'})
        self.cf.record['ttl']=900
        with self.assertRaises(Problem):infra.apply(self.store,self.config,{'confirm_plan_id':p['id']})
        self.assertEqual(self.cf.writes,0)
    def test_apply_verified_and_idempotent(self):
        p=self.plan()
        for _ in range(2):self.assertTrue(infra.apply(self.store,self.config,{'confirm_plan_id':p['id']})['applied'])
        self.assertEqual(self.cf.writes,1);self.assertEqual(self.cf.record['ttl'],600)
    def test_lost_response_reconciles_without_repeat(self):
        p=self.plan();self.cf.lose=True
        with self.assertRaises(infra.CloudflareError):infra.apply(self.store,self.config,{'confirm_plan_id':p['id']})
        with self.assertRaises(Problem):self.plan()
        self.assertEqual(infra.pending(self.store)['state'],'applying')
        self.assertTrue(infra.apply(self.store,self.config,{'confirm_plan_id':p['id']})['reconciled'])
        self.assertEqual(self.cf.writes,1)
    def test_unrelated_website_and_invalid_inputs_blocked(self):
        self.cf.record['name']='example.test'
        with self.assertRaises(Problem):self.plan()
        self.cf.record['name']='mail.example.test'
        for change in ({'content':'wrong-ip'},{'ttl':-1},{'proxied':True}):
            with self.assertRaises(Problem):infra.desired('dns',self.cf.record,change,'record')
        with self.assertRaises(Problem):infra.desired('route',{'ingress':[]},{'service':None},'t|mail.example.test')
    def test_routes_and_policy_preserve_other_configuration(self):
        before={'ingress':[{'hostname':'inbox.example.test','service':'http://old:80','originRequest':{'access':{'required':True}}},{'hostname':'site.example.test','service':'http://site:80'},{'service':'http_status:404'}]}
        after=infra.desired('route',before,{'service':'http://new:80'},'t|inbox.example.test')
        self.assertEqual(after['ingress'][1:],before['ingress'][1:]);self.assertEqual(after['ingress'][0]['originRequest'],before['ingress'][0]['originRequest'])
        policy={'name':'Owner','decision':'allow','include':[{'email':{'email':'owner@example.test'}}],'require':[{'email_domain':{'domain':'example.test'}}],'exclude':[]}
        changed=infra.desired('policy',policy,{'add_emails':['agent@example.test']},'a|p')
        self.assertEqual(changed['require'],policy['require']);self.assertEqual(changed['include'][0],policy['include'][0]);self.assertEqual(len(changed['include']),2)
        with self.assertRaises(Problem):infra.desired('policy',policy,{'decision':'bypass'},'a|p')
