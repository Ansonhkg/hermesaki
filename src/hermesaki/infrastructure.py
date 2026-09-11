"""Scoped Cloudflare edits with expiring plans and uncertain-write reconciliation."""
import fcntl
import ipaddress
import json
import secrets
import re
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from .store import Problem
from .setup_cloudflare import Cloudflare, CloudflareError, fingerprint
from .operator_configuration import read


def provider(store):
    with store.db() as db:
        row=db.execute("SELECT value FROM meta WHERE key='infrastructure_provider'").fetchone()
    if not row: raise Problem(409,'connect_cloudflare_first')
    return Cloudflare(store.open(row[0],'infrastructure_provider'))


def connect(store,config,data):
    token=data.get('token')
    if not isinstance(token,str) or not token or len(token)>4096: raise Problem(400,'provider_token_required')
    with locked(config):
        previous=pending(store)
        if previous and previous['state']=='applying': raise Problem(409,'reconcile_previous_change_first')
        cf=Cloudflare(token)
        result=inventory(store,config,cf)
        with store.db() as db:
            db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('infrastructure_provider',store.seal(token,'infrastructure_provider')))
        return result


def scope(config,cf):
    zones=[]
    labels=config.domain.split('.')
    for i in range(len(labels)-1):
        zones=cf.all('/zones',{'name':'.'.join(labels[i:])})
        if zones: break
    if len(zones)!=1 or zones[0].get('status')!='active': raise Problem(409,'active_zone_required')
    return zones[0]


def mail_record(config,r):
    name=r['name'];kind=r['type'];domain=config.domain
    return (name=='mail.'+domain and kind in ('A','AAAA') or name==domain and (kind=='MX' or kind=='TXT' and r.get('content','').startswith('v=spf1 ')) or name=='_dmarc.'+domain and kind=='TXT' or name.endswith('._domainkey.'+domain) and kind in ('TXT','CNAME'))


def inventory(store,config,cf=None):
    cf=cf or provider(store);z=scope(config,cf);prefix='/accounts/'+z['account']['id']
    hosts={urlsplit(config.public_url).hostname,urlsplit(read(config)['webmail_url']).hostname}-{None}
    records=cf.all('/zones/'+z['id']+'/dns_records')
    dns=[{k:r[k] for k in ('id','type','name','content','ttl','priority','proxied') if k in r} for r in records if mail_record(config,r)]
    apps=[a for a in cf.all(prefix+'/access/apps') if a.get('domain') in hosts]
    policies=[]
    for a in apps:
        for p in cf.all(prefix+'/access/apps/'+a['id']+'/policies'):
            policies.append({'app_id':a['id'],'hostname':a['domain'],**{k:p[k] for k in ('id','name','decision','include','exclude','require','precedence') if k in p}})
    tunnel_ids={r['content'].split('.')[0] for r in records if r['name'] in hosts and r['type']=='CNAME' and r['content'].endswith('.cfargotunnel.com')}
    routes=[]
    for tid in tunnel_ids:
        value=cf.call('GET',prefix+'/cfd_tunnel/'+tid+'/configurations')['result']['config']
        for route in value.get('ingress',[]):
            if route.get('hostname') in hosts:
                routes.append({'tunnel_id':tid,'hostname':route['hostname'],'service':route['service']})
    return {'checked_at':time.time(),'source':'Live Cloudflare API','dns':dns,'routes':routes,'policies':policies,'reads_only':True}


def resource(config,cf,kind,identity):
    z=scope(config,cf);prefix='/accounts/'+z['account']['id'];domain=config.domain
    if kind=='dns':
        path='/zones/'+z['id']+'/dns_records/'+identity
        r=cf.call('GET',path)['result']
        if not mail_record(config,r): raise Problem(403,'outside_mail_configuration')
        return path,{k:r[k] for k in ('type','name','content','ttl','priority','proxied','comment','tags','settings') if k in r}
    if kind=='route':
        if identity.count('|')!=1: raise Problem(400,'invalid_resource_id')
        tid,host=identity.split('|',1)
        allowed=inventory(None,config,cf)['routes']
        if not any(r['tunnel_id']==tid and r['hostname']==host for r in allowed): raise Problem(403,'outside_mail_configuration')
        path=prefix+'/cfd_tunnel/'+tid+'/configurations'
        return path,cf.call('GET',path)['result']['config']
    if kind=='policy':
        if identity.count('|')!=1: raise Problem(400,'invalid_resource_id')
        app,pid=identity.split('|',1)
        hosts={urlsplit(config.public_url).hostname,urlsplit(read(config)['webmail_url']).hostname}
        a=cf.call('GET',prefix+'/access/apps/'+app)['result']
        if a.get('domain') not in hosts: raise Problem(403,'outside_mail_configuration')
        path=prefix+'/access/apps/'+app+'/policies/'+pid
        p=cf.call('GET',path)['result']
        return path,{k:v for k,v in p.items() if k not in ('id','created_at','updated_at','app_count','reusable')}
    raise Problem(400,'unsupported_resource')


def desired(kind,before,change,identity):
    after=json.loads(json.dumps(before))
    if kind=='dns':
        if not set(change)<= {'content','ttl','priority'} or not change: raise Problem(400,'invalid_dns_change')
        if 'content' in change and (not isinstance(change['content'],str) or not change['content'] or len(change['content'])>4096): raise Problem(400,'invalid_dns_content')
        if 'ttl' in change and (type(change['ttl']) is not int or change['ttl']!=1 and not 60<=change['ttl']<=86400): raise Problem(400,'invalid_ttl')
        if 'priority' in change and (before['type']!='MX' or type(change['priority']) is not int or not 0<=change['priority']<=65535): raise Problem(400,'invalid_priority')
        after.update(change)
        if after['type'] in ('A','AAAA'):
            try: version=ipaddress.ip_address(after['content']).version
            except ValueError: raise Problem(400,'invalid_ip_address')
            if version != (4 if after['type']=='A' else 6): raise Problem(400,'invalid_ip_address')
        for prefix in ('v=spf1 ', 'v=DMARC1', 'v=DKIM1'):
            if before['content'].startswith(prefix) and not after['content'].startswith(prefix):
                raise Problem(400,'preserve_record_protocol')
    elif kind=='route':
        if set(change)!={'service'}: raise Problem(400,'invalid_route_change')
        if not isinstance(change['service'],str): raise Problem(400,'invalid_origin')
        try: u=urlsplit(change['service']);port=u.port
        except ValueError: raise Problem(400,'invalid_origin')
        if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.query or u.fragment: raise Problem(400,'invalid_origin')
        # Never remove a route, its authentication configuration, or its deny fallback.
        host=identity.split('|',1)[1]
        for r in after['ingress']:
            if r.get('hostname')==host:r['service']=change['service']
    else:
        if before.get('decision')!='allow' or not set(change)<= {'name','add_emails'} or not change:
            raise Problem(400,'preserve_existing_authorization')
        if 'name' in change:
            if not isinstance(change['name'],str) or not 1<=len(change['name'])<=100:raise Problem(400,'invalid_policy_name')
            after['name']=change['name']
        if 'add_emails' in change:
            emails=change['add_emails']
            if not isinstance(emails,list) or len(emails)>20 or any(not isinstance(e,str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",e) for e in emails):raise Problem(400,'invalid_email_list')
            for email in emails:
                rule={'email':{'email':email}}
                if rule not in after.setdefault('include',[]):after['include'].append(rule)
    return after


def save(store,p):
    with store.db() as db: db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('infrastructure_plan',json.dumps(p)))


@contextmanager
def locked(config):
    with open(Path(config.state)/'infrastructure.lock','a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        yield


def plan(store,config,data):
    kind=data.get('kind');identity=data.get('id');change=data.get('change')
    if kind not in ('dns','route','policy') or not isinstance(identity,str) or not isinstance(change,dict) or not identity or any(x in identity for x in ('/','?','#','..')): raise Problem(400,'invalid_change')
    with locked(config):
        with store.db() as db:
            previous=db.execute("SELECT value FROM meta WHERE key='infrastructure_plan'").fetchone()
        if previous and json.loads(previous[0])['state']=='applying':raise Problem(409,'reconcile_previous_change_first')
        cf=provider(store);path,before=resource(config,cf,kind,identity);after=desired(kind,before,change,identity)
        p={'id':secrets.token_hex(16),'kind':kind,'resource_id':identity,'path':path,'before':before,'after':after,'expires':time.time()+600,'state':'planned','warning':'DNS and origin changes can interrupt mail or access. Review the exact change before applying.'}
        save(store,p);return p


def apply(store,config,data):
    with locked(config):
        with store.db() as db:r=db.execute("SELECT value FROM meta WHERE key='infrastructure_plan'").fetchone()
        if not r:raise Problem(409,'plan_required')
        p=json.loads(r[0]);cf=provider(store)
        if data.get('confirm_plan_id')!=p['id']:raise Problem(409,'plan_mismatch')
        if p['state']=='applied':return {'applied':True,'reconciled':True}
        path,current=resource(config,cf,p['kind'],p['resource_id'])
        if p['state']=='applying':
            if fingerprint(current)==fingerprint(p['after']):p['state']='applied';save(store,p);return {'applied':True,'reconciled':True}
            raise Problem(409,'uncertain_change_inspect_provider_before_retry')
        if time.time()>p['expires'] or fingerprint(current)!=fingerprint(p['before']):raise Problem(409,'stale_plan_review_again')
        p['state']='applying';save(store,p)
        cf.call('PUT',path,{'config':p['after']} if p['kind']=='route' else p['after'])
        _,current=resource(config,cf,p['kind'],p['resource_id'])
        if fingerprint(current)!=fingerprint(p['after']):raise Problem(409,'provider_verification_required')
        p['state']='applied';save(store,p)
        return {'applied':True}


def pending(store):
    with store.db() as db: r=db.execute("SELECT value FROM meta WHERE key='infrastructure_plan'").fetchone()
    return json.loads(r[0]) if r else None
