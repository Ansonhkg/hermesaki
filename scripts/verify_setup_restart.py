"""Live crash/restart check on an explicitly authorized, unused test subdomain."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hermesaki.setup import Setup
from hermesaki.setup_cloudflare import Cloudflare

p = argparse.ArgumentParser()
p.add_argument('--state', required=True)
p.add_argument('--settings', required=True)
p.add_argument('--confirm-isolated-domain', required=True)
p.add_argument('--child', action='store_true')
a = p.parse_args()
root = Path(a.state).resolve()
settings = json.loads(Path(a.settings).read_text())
if settings['domain'] != a.confirm_isolated_domain:
    raise SystemExit('Exact isolated domain confirmation required')

def trace(label, value):
    print(label + ': ' + json.dumps(value, sort_keys=True), flush=True)

class CrashAfterTunnel(Cloudflare):
    def apply(self, settings, plan, progress, checkpoint):
        def saved(value):
            checkpoint(value)
            if value['steps'].get('tunnel') and len(value['steps']) == 1 and not value.get('inflight'):
                os.kill(os.getpid(), signal.SIGKILL)
        return super().apply(settings, plan, progress, saved)

if a.child:
    setup = Setup(root, CrashAfterTunnel)
    owner = (root / 'test-owner').read_text()
    state = setup.call('GET', '/v1/setup', owner, {})
    trace('Child PID applying saved plan', {'pid':os.getpid(), 'plan_id':state['cloudflare_plan']['id']})
    setup.call('POST', '/v1/setup/apply', owner, {'confirm_plan_id': state['cloudflare_plan']['id']})
    raise SystemExit('Fault injection did not occur')

if root.exists():
    raise SystemExit('Existing verification state retained; choose a new path')
cf = Cloudflare(os.environ['HERMESAKI_SETUP'])
if cf.all('/zones', {'name':settings['domain']}):
    raise SystemExit('Only isolated subdomains may be used')
preview = cf.plan(settings)
if not all(x['operation'] == 'create' for x in preview['actions']):
    raise SystemExit('Use an unused test subdomain')
setup = Setup(root)
owner = secrets.token_urlsafe(32)
fd = os.open(root / 'test-owner', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, 'w') as f: f.write(owner)
setup.call('POST','/v1/setup/claim',(root/'bootstrap-token').read_text(),{'owner_token':owner})
setup.call('PUT','/v1/setup/configuration',owner,settings)
plan = setup.call('PUT','/v1/setup/cloudflare',owner,{'token':cf.token})['plan']
secret_digest = hashlib.sha256((root/'cloudflare-token').read_bytes()).digest()
trace('Launching fresh setup process', {'state':str(root),'plan_id':plan['id']})
child = subprocess.run([sys.executable, __file__, '--state',str(root),'--settings',a.settings,'--confirm-isolated-domain',a.confirm_isolated_domain,'--child'], capture_output=True)
print(child.stdout.decode(),end='',flush=True)
trace('Observed process exit',child.returncode)
assert child.returncode == -signal.SIGKILL, 'Expected actual process SIGKILL'
setup = Setup(root)
interrupted = setup.call('GET','/v1/setup',owner,{})
trace('Reopened setup GET provisioning',interrupted['provisioning'])
assert list(interrupted['provisioning']['steps']) == ['tunnel']
assert not interrupted['complete']
result = setup.call('POST','/v1/setup/apply',owner,{'confirm_plan_id':plan['id']})
trace('Actual resumed apply response',result)
resumed = setup.call('GET','/v1/setup',owner,{})
assert result['progress']['state'] == 'web_resources_applied'
assert not result['complete']
assert secret_digest == hashlib.sha256((root/'cloudflare-token').read_bytes()).digest()
def inventory():
    fresh = cf.plan(settings)
    tunnels = cf.all('/accounts/'+plan['account_id']+'/cfd_tunnel',{'is_deleted':'false'})
    apps = cf.all('/accounts/'+plan['account_id']+'/access/apps')
    hosts = ['inbox.'+settings['domain'],'hermesaki.'+settings['domain']]
    records = cf.all('/zones/'+plan['zone_id']+'/dns_records')
    data = {'tunnels':[t['id'] for t in tunnels if t['name']=='hermesaki-'+settings['domain']], 'access_apps': sorted(t['id'] for t in apps if t.get('domain') in hosts), 'dns_records':sorted(t['id'] for t in records if t['name'] in hosts)}
    assert [len(data[k]) for k in ['tunnels','access_apps','dns_records']] == [1,2,2]
    assert all(x['operation']=='reuse' for x in fresh['actions'])
    return data
before = inventory()
trace('Cloudflare GET inventory before repeat',before)
Setup(root).call('POST','/v1/setup/apply',owner,{'confirm_plan_id':plan['id']})
after = inventory()
trace('Cloudflare GET inventory after repeat',after)
assert before == after
report = {'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'Real Cloudflare API; actual SIGKILL after durable tunnel checkpoint; fresh Setup instance reopened persisted SQLite. No provider mock.', 'process_exit':child.returncode, 'interrupted':{k:interrupted[k] for k in ['complete','provisioning']}, 'resumed':result, 'repeat_before':before,'repeat_after':after,'credential_preserved':True,'credential_mode':oct((root/'cloudflare-token').stat().st_mode & 0o777),'scope':'Web provisioning only. Full service setup remains explicitly incomplete.'}
(root/'report.json').write_text(json.dumps(report,indent=2))
trace('Private credential remained usable after restart', {'preserved':report['credential_preserved'],'mode':report['credential_mode'],'complete':result['complete']})
print('Recorded output: '+str(root/'report.json'))
