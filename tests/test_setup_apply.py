import copy
import unittest
from hermesaki.setup_cloudflare import Cloudflare, CloudflareError


class Fixture(Cloudflare):
    def __init__(self):
        self.token='fixture';self.tunnels=[];self.apps=[];self.policies={};self.config={'ingress':[{'service':'http_status:404'}]};self.records=[];self.writes=[];self.serial=0
    def validate_access_team(self,hostname,team):return True  # Explicit external provider fixture.
    def all(self,path,query=None):
        if path=='/zones':return [{'id':'zone','name':'example.com','status':'active','account':{'id':'account'}}]
        if path.endswith('/access/apps'):return copy.deepcopy(self.apps)
        if path.endswith('/policies'):return copy.deepcopy(self.policies[path.split('/')[-2]])
        if path.endswith('/cfd_tunnel'):return copy.deepcopy(self.tunnels)
        if path.endswith('/dns_records'):return copy.deepcopy([r for r in self.records if r['name']==query['name']])
        raise AssertionError(path)
    def call(self,method,path,body=None,query=None):
        if method=='GET' and path.endswith('/configurations'):return {'result':{'config':copy.deepcopy(self.config)}}
        self.writes.append((method,path,copy.deepcopy(body)));self.serial+=1;ident=str(self.serial)
        if method=='DELETE':
            ident=path.split('/')[-1]
            if '/dns_records/' in path:self.records=[r for r in self.records if r.get('id')!=ident]
            elif '/access/apps/' in path:self.apps=[a for a in self.apps if a['id']!=ident];self.policies.pop(ident,None)
            elif '/cfd_tunnel/' in path:self.tunnels=[t for t in self.tunnels if t['id']!=ident]
            else:raise AssertionError(path)
            return {'success':True,'result':{'id':ident}}
        if method=='POST' and path.endswith('/cfd_tunnel'):
            value={'id':ident,**body};self.tunnels.append(value)
        elif method=='POST' and path.endswith('/access/apps'):
            value={'id':ident,**body};self.apps.append(value);self.policies[ident]=body['policies']
        elif method=='PUT' and path.endswith('/configurations'):
            self.config=copy.deepcopy(body['config']);value=body
        elif method=='POST' and path.endswith('/dns_records'):
            value={'id':ident,**body};self.records.append(value)
        else:raise AssertionError((method,path))
        return {'success':True,'result':copy.deepcopy(value)}


class Apply(unittest.TestCase):
    settings={'domain':'example.com','server_ip':'203.0.113.10','owner_email':'owner@example.com'}
    def test_access_before_dns_resume_and_preserve_unrelated_records(self):
        f=Fixture();unrelated={'name':'example.com','type':'A','content':'203.0.113.40'};f.records.append(unrelated)
        plan=f.plan(self.settings);progress={};checkpoints=[]
        result=f.apply(self.settings,plan,progress,lambda p:checkpoints.append(copy.deepcopy(p)))
        self.assertEqual(result['state'],'web_resources_applied')
        writes=len(f.writes)
        f.apply(self.settings,plan,progress,lambda p:None)
        self.assertEqual(len(f.writes),writes)
        self.assertIn(unrelated,f.records)
        production=[w for w in f.writes if not (w[2] or {}).get('name','').startswith('hermesaki-check-')]
        access=[i for i,(_,p,_) in enumerate(production) if p.endswith('/access/apps')]
        dns=[i for i,(_,p,_) in enumerate(production) if p.endswith('/dns_records')]
        self.assertLess(max(access),min(dns))
        self.assertTrue(checkpoints)
        refreshed=f.plan(self.settings)
        self.assertFalse(refreshed['conflicts'])
        self.assertTrue(all(a['operation']=='reuse' for a in refreshed['actions']))

    def test_changed_remote_state_requires_review_before_any_write(self):
        f=Fixture();plan=f.plan(self.settings)
        f.records.append({'name':'inbox.example.com','type':'A','content':'203.0.113.7'})
        with self.assertRaisesRegex(CloudflareError,'plan_changed'):
            f.apply(self.settings,plan,{},lambda p:None)
        self.assertFalse(f.writes)

    def test_conflicting_access_denied_and_not_overwritten(self):
        f=Fixture();f.apps=[{'id':'other','domain':'inbox.example.com','type':'self_hosted'}];f.policies['other']=[{'decision':'bypass','include':[{'everyone':{}}]}]
        plan=f.plan(self.settings)
        with self.assertRaisesRegex(CloudflareError,'plan_has_conflicts'):f.apply(self.settings,plan,{},lambda p:None)
        self.assertFalse(f.writes)

    def test_resume_after_acknowledged_step(self):
        f=Fixture();plan=f.plan(self.settings);persisted={}
        def checkpoint(p):
            persisted.clear();persisted.update(copy.deepcopy(p))
            if p['steps'].get('tunnel') and len(p['steps'])==1 and not p.get('inflight'):raise InterruptedError('process interrupted')
        with self.assertRaises(InterruptedError):f.apply(self.settings,plan,{},checkpoint)
        f.apply(self.settings,plan,persisted,lambda p:None)
        self.assertEqual(len(f.tunnels),1)
        self.assertEqual(len(f.apps),2)
        self.assertEqual(len(f.records),2)

    def test_uncertain_write_is_not_repeated(self):
        f=Fixture();plan=f.plan(self.settings);progress={}
        original=f.call
        def uncertain(method,path,body=None,query=None):
            result=original(method,path,body,query)
            if method=='POST':raise CloudflareError('cloudflare_unavailable')
            return result
        f.call=uncertain
        with self.assertRaises(CloudflareError):f.apply(self.settings,plan,progress,lambda p:None)
        f.call=original
        with self.assertRaisesRegex(CloudflareError,'uncertain_permission_probe'):f.apply(self.settings,plan,progress,lambda p:None)
        self.assertEqual(len(f.records),1)
        self.assertFalse(f.tunnels)

    def test_missing_write_permission_cleans_probes_before_live_changes(self):
        f=Fixture();plan=f.plan(self.settings);original=f.call;progress={}
        def denied(method,path,body=None,query=None):
            if method=='POST' and path.endswith('/access/apps'):raise CloudflareError('cloudflare_permission_denied')
            return original(method,path,body,query)
        f.call=denied
        with self.assertRaisesRegex(CloudflareError,'write_permission_required'):
            f.apply(self.settings,plan,progress,lambda p:None)
        self.assertFalse(f.records);self.assertFalse(f.tunnels);self.assertFalse(f.apps)
        self.assertFalse(progress['steps']);self.assertEqual(progress['permission_probe']['state'],'failed')
        f.call=original
        f.apply(self.settings,plan,progress,lambda p:None)
        self.assertEqual(progress['permission_probe']['state'],'passed')
        self.assertEqual(len(f.records),2)

    def test_cleanup_failure_blocks_provisioning_until_retry(self):
        f=Fixture();plan=f.plan(self.settings);original=f.call;progress={}
        def denied(method,path,body=None,query=None):
            if method=='DELETE':raise CloudflareError('cloudflare_permission_denied')
            return original(method,path,body,query)
        f.call=denied
        with self.assertRaisesRegex(CloudflareError,'cleanup_required'):
            f.apply(self.settings,plan,progress,lambda p:None)
        self.assertFalse(progress['steps']);self.assertTrue(progress['permission_probe']['resources'])
        f.call=original
        f.apply(self.settings,plan,progress,lambda p:None)
        self.assertEqual(len(f.records),2);self.assertEqual(len(f.apps),2);self.assertEqual(len(f.tunnels),1)
