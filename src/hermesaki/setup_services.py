"""Fresh-install planning. Never adopt or overwrite an existing mail deployment."""
import ipaddress
import json
import os
import re
from pathlib import Path
from .setup_cloudflare import CloudflareError, fingerprint


class DeploymentError(Exception):
    pass


def private_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.new')
    fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def validate_options(data, settings):
    if set(data) != {'access_team', 'first_mailbox', 'accept_acme_terms'}:
        raise DeploymentError('expected_access_team_first_mailbox_accept_acme_terms')
    team, mailbox = data['access_team'], data['first_mailbox']
    if not isinstance(team, str) or not re.fullmatch(r'[a-z0-9-]{1,63}', team):
        raise DeploymentError('invalid_access_team')
    if not isinstance(mailbox, str) or not re.fullmatch(r'[a-z0-9][a-z0-9._+-]{0,63}@' + re.escape(settings['domain']), mailbox):
        raise DeploymentError('first_mailbox_must_belong_to_domain')
    if data['accept_acme_terms'] is not True:
        raise DeploymentError('acme_terms_acceptance_required')
    return dict(data)


def records_for(settings):
    domain, address = settings['domain'], ipaddress.ip_address(settings['server_ip'])
    return [
        {'type': 'A' if address.version == 4 else 'AAAA', 'name': 'mail.'+domain, 'content': str(address), 'proxied': False, 'ttl': 300},
        {'type': 'MX', 'name': domain, 'content': 'mail.'+domain, 'priority': 10, 'ttl': 300},
        {'type': 'TXT', 'name': domain, 'content': 'v=spf1 '+('ip4:' if address.version == 4 else 'ip6:')+str(address)+' -all', 'ttl': 300},
        {'type': 'TXT', 'name': '_dmarc.'+domain, 'content': 'v=DMARC1; p=none', 'ttl': 300},
    ]


def related(record, desired):
    if desired['type'] in ('A', 'AAAA'):
        return record['type'] in ('A','AAAA','CNAME')
    if record['type'] == 'CNAME':
        return True
    if desired['type'] == 'TXT' and desired['content'].startswith('v=spf1'):
        return record['type'] == 'TXT' and record.get('content','').strip('"').lower().startswith('v=spf1')
    return record['type'] == desired['type']


def compatible(record, desired):
    keys = ['type','content'] + (['priority'] if desired['type']=='MX' else [])
    if not all(str(record.get(k,'')).strip('"').rstrip('.') == str(desired[k]).rstrip('.') for k in keys):
        return False
    return desired['type'] not in ('A','AAAA') or record.get('proxied') is False


def dns_plan(provider, zone, desired_records):
    actions, conflicts, observed = [], [], []
    for desired in desired_records:
        records = provider.all('/zones/'+zone+'/dns_records', {'name':desired['name']})
        candidates = [r for r in records if related(r,desired)]
        reuse = len(candidates)==1 and compatible(candidates[0],desired)
        operation = 'reuse' if reuse else 'conflict' if candidates else 'create'
        if operation == 'conflict':
            conflicts.append(desired['name']+': existing '+desired['type']+' differs; existing mail DNS will not be overwritten.')
        actions.append({'kind':'mail_dns','operation':operation,'record':desired})
        observed.append({'desired':desired,'existing':candidates})
    return actions, conflicts, observed


class Services:
    def __init__(self, directory, repository=None):
        self.directory = Path(directory).resolve()
        self.root = self.directory / 'installation'
        self.repository = Path(repository or Path(__file__).resolve().parents[2])

    def plan(self, provider, settings, web_plan, progress, options):
        options = validate_options(options, settings)
        if not progress or progress.get('state') != 'web_resources_applied':
            raise DeploymentError('apply_web_protection_first')
        current = provider.plan(settings)
        if current['conflicts'] or any(a['operation']!='reuse' for a in current['actions']):
            raise DeploymentError('web_protection_changed')
        actions, conflicts, observed = dns_plan(provider,web_plan['zone_id'],records_for(settings))
        if hasattr(provider,'validate_access_team') and not provider.validate_access_team('hermesaki.'+settings['domain'],options['access_team']):
            conflicts.append('The operator hostname does not redirect to this Access team. Correct the team name or wait for web DNS to propagate, then refresh the plan.')
        if self.root.exists() and not (self.root/'owned-plan').exists() and any(self.root.iterdir()):
            conflicts.append('Installation directory is not owned by this setup. Existing data will not be adopted.')
        lock = json.loads((self.repository/'components.lock.json').read_text())
        plan = {'scope':'fresh_mail_installation','zone_id':web_plan['zone_id'],'account_id':web_plan['account_id'],
            'tunnel_id':progress['tunnel_id'],'options':options,'actions':actions,
            'services':{'mail':{'image':lock['stalwart']['image'],'published_ports':[{'ip':settings['server_ip'],'port':25}], 'hostname':'mail.'+settings['domain']},
                'api':{'source':'docker/api/Dockerfile','published_ports':[],'application_auth':'Cloudflare JWT plus scoped bearer token'},
                'worker':{'source':'docker/api/Dockerfile','published_ports':[]},
                'webmail':{'image':lock['roundcube']['image'],'published_ports':[],'application_auth':'Mailbox password'},
                'tunnel':{'image':lock['cloudflared']['image'],'published_ports':[]}},
            'certificate':{'hostname':'mail.'+settings['domain'],'issuer':'Let\'s Encrypt','challenge':'Cloudflare DNS-01','contact':settings['owner_email'],'renewal':'Certbot every 12 hours; verified certificate sync every minute','image':lock['certbot']['image']},
            'storage':str(self.root),'first_mailbox':options['first_mailbox'],
            'conflicts':conflicts,'apply_available':not conflicts,
            'remaining':['Review generated DKIM DNS after mail initialization.','Verify external mail, certificate renewal and protected access before completion.']}
        plan['id'] = fingerprint({'settings':settings,'plan':plan,'observed':observed})
        return plan

    def apply_dns(self, provider, plan, progress, checkpoint):
        """Reconcile exact desired records after a lost response, never overwrite."""
        for action in plan['actions']:
            record=action['record']; key=record['type']+':'+record['name']
            actions, conflicts, _=dns_plan(provider,plan['zone_id'],[record])
            if conflicts:
                raise DeploymentError('mail_dns_changed_review_required')
            if actions[0]['operation']=='create':
                if key in progress.get('dns_inflight',[]):
                    raise DeploymentError('uncertain_mail_dns_write_review_required')
                progress.setdefault('dns_inflight',[]).append(key);checkpoint(progress)
                provider.call('POST','/zones/'+plan['zone_id']+'/dns_records',record)
                verified,conflicts,_=dns_plan(provider,plan['zone_id'],[record])
                if conflicts or verified[0]['operation']!='reuse':
                    raise DeploymentError('mail_dns_verification_failed')
            if key in progress.get('dns_inflight',[]):progress['dns_inflight'].remove(key)
            progress.setdefault('dns',{})[key]='verified';checkpoint(progress)
