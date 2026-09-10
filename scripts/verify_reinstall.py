#!/usr/bin/env python3
"""Back up a live deployment and prove restoration on an internal-only network.

No restored worker, tunnel or public ports are started. The live stack is paused
only while capturing its consistent encrypted snapshot, then immediately resumed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
from reinstall import snapshot, restore, compose

VERIFY = '''import json,hashlib
from hermesaki.config import Config
from hermesaki.store import Store
from hermesaki.mail import Mail,Stalwart
from pathlib import Path
c=Config.load();s=Store('/state');m=Mail(c,s)
a=json.loads(Path('/state/management.json').read_text())
domains=Stalwart(c.management_url,a['username'],a['password'],c.ca_file).list('Domain')
with s.db() as db:ids=[r[0] for r in db.execute('SELECT id FROM inboxes')]
mailboxes=[]
for ident in ids:
 inbox=s.inbox(ident)
 with m.connect(inbox) as client:
  folders=client.list()[1];client.select('INBOX',readonly=True);uids=client.uid('search',None,'ALL')[1][0]
  hashes=[]
  for uid in uids.split():
   status,data=client.uid('fetch',uid,'(BODY.PEEK[])')
   assert status=='OK'
   hashes.append(hashlib.sha256(b''.join(x[1] for x in data if isinstance(x,tuple))).hexdigest())
 mailboxes.append({'id':ident,'folders':len(folders),'messages':len(hashes),'content_sha256':hashlib.sha256(json.dumps(hashes).encode()).hexdigest()})
print(json.dumps({'production_mode':c.mode=='production','development_auth_disabled':not c.dev_auth,'domains':sorted(d['name'] for d in domains),'mailboxes':mailboxes}))
'''


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--confirm-source',required=True)
    ap.add_argument('--archive',type=Path,required=True)
    ap.add_argument('--key-file',type=Path,required=True)
    ap.add_argument('--destination',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True)
    args=ap.parse_args()
    if str(args.source)!=args.confirm_source:raise ValueError('exact source confirmation required')
    transcript=[]
    def check(path):
        result=subprocess.run(
            ['docker','compose','-f',str(path),'exec','-T','api','python','-'],input=VERIFY.encode(),capture_output=True,check=True)
        return json.loads(result.stdout)
    before=check(args.source)
    transcript.append({'command':'verify source via TLS IMAP BODY.PEEK and Stalwart domain API','result':before})
    backup=snapshot(args.source,args.archive,args.key_file)
    transcript.append({'command':'reinstall.snapshot (pause, archive every bind, encrypt, unpause)','result':backup})
    path=restore(args.archive,args.key_file,args.destination,args.source.parent)
    config=json.loads(path.read_text());config['name']='hermesaki-restore-'+hashlib.sha256(str(path).encode()).hexdigest()[:10]
    config['services']={k:v for k,v in config['services'].items() if k in ('mail','api','webmail')}
    state=next(v.split(':')[0] for v in config['services']['api']['volumes'] if v.split(':')[1]=='/state')
    settings=json.loads(Path(state,'config.json').read_text());hostname=settings['mail_host']
    for name,service in config['services'].items():
        for key in ('ports','build','depends_on','network_mode'):service.pop(key,None)
        service['restart']='no'
        service['networks']={'isolated':{'aliases':[hostname]}} if name=='mail' else ['isolated']
    config['networks']={'isolated':{'internal':True}}
    path.write_text(json.dumps(config))
    try:
        compose(path,'up','-d')
        for attempt in range(40):
            try:after=check(path);break
            except subprocess.CalledProcessError:
                if attempt==39:raise
                time.sleep(1)
        assert before==after,'restored mailbox or domain data differs'
        ids=compose(path,'ps','-q').decode().split()
        actual=json.loads(subprocess.check_output(['docker','inspect',*ids]))
        networks={n for c in actual for n in c['NetworkSettings']['Networks']}
        network_details=json.loads(subprocess.check_output(['docker','network','inspect',*networks]))
        assert all(n['Internal'] for n in network_details)
        assert all(not c['HostConfig']['PortBindings'] for c in actual)
        transcript.append({'command':'docker inspect restored containers/networks','result':{'containers':[{'name':c['Name'],'image':c['Config']['Image'],'state':c['State']['Status'],'port_bindings':c['HostConfig']['PortBindings']} for c in actual],'networks':[{'name':n['Name'],'internal':n['Internal']} for n in network_details]}})
        transcript.append({'command':'verify restored instance via TLS IMAP BODY.PEEK and Stalwart domain API','result':after})
        compose(path,'restart')
        for attempt in range(40):
            try:restarted=check(path);break
            except subprocess.CalledProcessError:
                if attempt==39:raise
                time.sleep(1)
        assert restarted==after
        transcript.append({'command':'docker compose restart; repeat authenticated content verification','result':restarted})
    finally:
        compose(path,'down')
    live=check(args.source)
    transcript.append({'command':'verify live source is still available after rehearsal','result':live})
    report={'source':str(args.source),'archive':str(args.archive),'restored':str(path),'transcript':transcript,'isolated_restore_passed':True}
    args.report.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
