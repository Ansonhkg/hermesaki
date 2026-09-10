"""Observed deployment readiness. Never converts an untested check into success."""
import json
import time
import socket
import urllib.error
import urllib.parse
import urllib.request
from .setup_services import DeploymentError
from .setup_cloudflare import web_hosts
from .setup_dns import public_dns


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def verify(runtime,settings,plan,dkim_published,renewal_verified,network=None,agent=None,mail=None):
    checks=[]
    def add(name,state,detail):checks.append({'id':name,'state':state,'detail':detail})
    script='''import json,time,urllib.request
from pathlib import Path
from hermesaki.http import create_app
app=create_app();s=app.s.store
account=json.loads(Path('/state/first-mailbox.json').read_text())
folders=app.s.mail.folders(s.inbox(account['id']))
health=Path('/state/certificate-health.json')
print(json.dumps({'mailbox':bool(folders),'webmail':urllib.request.urlopen('http://webmail/',timeout=10).status,'certificate':json.loads(health.read_text()) if health.exists() else None}))
'''
    try:
        result=json.loads(runtime.dc('exec','-T','api','python','-',stdin=script))
        add('mailbox','passed' if result['mailbox'] else 'failed','Mailbox login and folders checked over verified TLS.')
        add('webmail','passed' if result['webmail']==200 else 'failed','Private webmail responds.')
        certificate=result.get('certificate') or {}
        good=certificate.get('status')=='verified' and time.time()-certificate.get('checked_at',0)<180
        add('tls','passed' if good else 'pending','Certificate sync must recently verify the served certificate.')
    except (DeploymentError,ValueError,KeyError):
        add('mailbox','failed','Private mailbox or webmail check failed; retry after services are healthy.')
        add('webmail','pending','Private webmail is not yet verified.')
        add('tls','pending','Served certificate has not been verified.')
    protected=True
    for host in web_hosts(settings):
        try:
            urllib.request.build_opener(NoRedirect()).open(urllib.request.Request('https://'+host,headers={'User-Agent':'Hermesaki-Setup/1.0'}),timeout=15)
            protected=False
        except urllib.error.HTTPError as error:
            expected='https://'+plan['options']['access_team']+'.cloudflareaccess.com/'
            if error.code not in (301,302,303,307,308) or not error.headers.get('Location','').startswith(expected):protected=False
        except (OSError,ValueError):protected=False
    add('anonymous_access','passed' if protected else 'failed','Both web hostnames must redirect anonymous visitors to the configured Access team.')
    try:
        output=runtime.dc('ps','--format','json').strip()
        rows=json.loads(output) if output.startswith('[') else [json.loads(line) for line in output.splitlines()]
        exposed=[p for row in rows for p in (row.get('Publishers') or []) if p.get('PublishedPort')]
        safe=bool(rows) and all(p.get('PublishedPort')==25 for p in exposed)
        add('origin_ports','passed' if safe else 'failed','Docker must publish only SMTP port 25; no direct HTTP origin.')
    except (DeploymentError,ValueError,TypeError):add('origin_ports','failed','Actual published ports could not be verified.')
    add('dkim','passed' if dkim_published else 'pending','Public signing records must be reviewed and published.')
    add('renewal','passed' if renewal_verified else 'pending','Run a real ACME renewal dry-run from the setup screen.')
    checks.append(public_dns(settings))
    if mail and mail.get('plan_id')==plan['id'] and 0<=time.time()-mail.get('checked_at',0)<86400:
        checks.append(mail)
    else:
        add('external_mail','pending','Send the external test, reply to it and upload the received original to verify authentication.')
    if agent and agent.get('plan_id')==plan['id'] and 0<=time.time()-agent.get('checked_at',0)<300:
        checks.append(agent)
    else:
        add('authenticated_agent','pending','Verify the remote agent connection using an authorized Access service token. Results expire after five minutes.')
    if network and network.get('plan_id')==plan['id'] and 0<=time.time()-network.get('checked_at',0)<86400:
        network=dict(network)
        if network['state']=='passed':
            try:
                with socket.create_connection(('gmail-smtp-in.l.google.com',25),timeout=5):pass
                network['detail']+=' Outbound SMTP connection from installation host succeeded.'
            except OSError:
                network.update(state='pending',detail='External inbound check passed, but outbound SMTP connection failed. Check provider port-25 restrictions.')
        checks.append(network)
    else:
        add('provider_network','pending','Download a network probe challenge, run it on a separate public host and upload the signed result.')
    return {'checks':checks,'ready':all(c['state']=='passed' for c in checks),'complete':False,'checked_at':int(time.time()),'next_action':'resolve_pending_checks'}
