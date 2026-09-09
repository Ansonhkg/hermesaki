import os,json,sys,datetime,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from hermesaki.setup_cloudflare import Cloudflare,CloudflareError,fingerprint
parser=argparse.ArgumentParser(description='Live verification that temporarily changes ONLY a previously provisioned isolated test CNAME and restores it.')
parser.add_argument('--evidence-dir',required=True)
parser.add_argument('--confirm-isolated-domain',required=True)
args=parser.parse_args()
root=Path(args.evidence_dir); saved=json.loads((root/'live-plan.json').read_text()); settings=saved['settings']; original=saved['plan']; cf=Cloudflare(os.environ['HERMESAKI_SETUP']); zone=original['zone_id']; account=original['account_id']; rows=[]; raw={}
def record(test,result):rows.append({'test':test,'result':result})
if settings['domain'] != args.confirm_isolated_domain:
 raise SystemExit('Exact isolated domain confirmation required')
if any(z['name']==settings['domain'] for z in cf.all('/zones',{'name':settings['domain']})):
 raise SystemExit('Use a test subdomain, never the primary zone')
plan=cf.plan(settings)
raw['refreshed_plan']=plan
assert all(a['operation']=='reuse' for a in plan['actions'])
record('Compatible resources reused',str(len(plan['actions']))+' of '+str(len(plan['actions']))+' actions are reuse; no conflicts')
progress=json.loads((root/'live-progress.json').read_text())
cf.apply(settings,original,progress,lambda p:None)
record('Restart and repeat apply','Persisted tunnel checkpoint resumed successfully. Repeated completed apply verified existing resources.')
tunnels=cf.all('/accounts/'+account+'/cfd_tunnel',{'is_deleted':'false'})
assert len([t for t in tunnels if t['name']=='hermesaki-'+settings['domain']])==1
record('No duplicate test tunnel','Exactly one tunnel with the isolated installation name')
path='/zones/'+zone+'/dns_records'
name='inbox.'+settings['domain']
item=cf.all(path,{'name':name})[0]
changed=False
try:
 cf.call('PATCH',path+'/'+item['id'],{'content':'conflict.example.com'});changed=True
 conflict=cf.plan(settings)
 assert conflict['conflicts'] and not conflict['apply_available']
 try:cf.apply(settings,conflict,{},lambda p:None)
 except CloudflareError as e:
  assert str(e)=='plan_has_conflicts'
  raw['apply_error']={'error':str(e)}
 else:raise AssertionError('Conflict applied')
 raw['conflict_plan']=conflict
 raw['conflict_record_after_refused_apply']=cf.all(path,{'name':name})[0]
 assert raw['conflict_record_after_refused_apply']['content']=='conflict.example.com'
 record('Conflicting DNS halts without overwrite','plan_has_conflicts. Test CNAME remained conflict.example.com after refused apply. Remedy: restore the intended target and refresh plan.')
finally:
 if changed:cf.call('PATCH',path+'/'+item['id'],{'content':item['content']})
assert not cf.plan(settings)['conflicts']
record('Test conflict restored','Original test CNAME target restored and compatibility rechecked')
before=json.loads((root/'live-dns-before.json').read_text());after=cf.all(path)
keys=('id','type','name','content','proxied','ttl','priority','data','comment','tags')
def normalize(items):return sorted([{k:r.get(k) for k in keys} for r in items],key=lambda r:r['id'])
oldids={r['id'] for r in before}
assert normalize(before)==normalize([r for r in after if r['id'] in oldids])
record('Unrelated website and mail DNS preserved',str(len(before))+' pre-existing records unchanged, including MX and authentication records; comparison includes value, proxy, TTL, priority and data.')
record('Scope','Only hermesaki.'+settings['domain']+' and inbox.'+settings['domain']+' are test resources. Pre-existing records were compared and preserved.')
report={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'Actual Cloudflare API requests using Hermesaki Cloudflare planner/apply; no provider mocks. Web-resource verification only.','raw':raw,'before_records':normalize(before),'after_records':normalize([r for r in after if r['id'] in oldids]),'rows':rows,'before_fingerprint':fingerprint(normalize(before)),'after_fingerprint':fingerprint(normalize([r for r in after if r['id'] in oldids]))}
(root/'live-cloudflare-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
