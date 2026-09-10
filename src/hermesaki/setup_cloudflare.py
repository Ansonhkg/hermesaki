"""Cloudflare web-protection plans. No mail delivery records are changed."""
import copy
import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request


def web_hosts(settings):
    return (settings.get('operator_hostname','hermesaki.'+settings['domain']),
            settings.get('webmail_hostname','inbox.'+settings['domain']))


class CloudflareError(Exception):
    pass


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def owner_policy(app, policies, email):
    return (app.get('type') == 'self_hosted' and len(policies) == 1
        and policies[0].get('decision') == 'allow'
        and policies[0].get('include') == [{'email': {'email': email}}]
        and not policies[0].get('exclude') and not policies[0].get('require')
        and not app.get('skip_app_launcher_login')
        and not app.get('service_auth_401_redirect'))


class Cloudflare:
    def __init__(self, token):
        self.token = token

    def validate_access_team(self, hostname, team):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):return None
        try:
            urllib.request.build_opener(NoRedirect()).open(urllib.request.Request('https://'+hostname,headers={'User-Agent':'Hermesaki-Setup/1.0'}), timeout=15)
        except urllib.error.HTTPError as error:
            return error.code in (301,302,303,307,308) and error.headers.get('Location','').startswith('https://'+team+'.cloudflareaccess.com/')
        except (OSError,ValueError):
            return False
        return False

    def call(self, method, path, body=None, query=None):
        url = 'https://api.cloudflare.com/client/v4' + path
        if query:
            url += '?' + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, method=method,
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'},
            data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                value = json.load(response)
        except urllib.error.HTTPError as error:
            raise CloudflareError('cloudflare_permission_denied' if error.code in (401,403) else 'cloudflare_request_failed') from None
        except (OSError, ValueError):
            raise CloudflareError('cloudflare_unavailable') from None
        if not value.get('success'):
            raise CloudflareError('cloudflare_request_failed')
        return value

    def all(self, path, query=None):
        rows = []
        for page in range(1, 101):
            value = self.call('GET', path, query={**(query or {}), 'page':page, 'per_page':50})
            rows.extend(value['result'])
            pages = value.get('result_info', {}).get('total_pages')
            if (pages is not None and page >= pages) or len(value['result']) < 50:
                return rows
        raise CloudflareError('too_many_cloudflare_resources')

    def plan(self, settings):
        # A mail domain can be an isolated subdomain of the authorized DNS zone.
        zones = []
        labels = settings['domain'].split('.')
        for index in range(len(labels) - 1):
            name = '.'.join(labels[index:])
            zones = [z for z in self.all('/zones', {'name':name}) if z['name'] == name]
            if zones:
                break
        if len(zones) != 1 or zones[0].get('status') != 'active':
            raise CloudflareError('active_domain_zone_required')
        zone = zones[0]
        account = zone['account']['id']
        prefix = '/accounts/' + account
        apps = self.all(prefix + '/access/apps')
        tunnels = self.all(prefix + '/cfd_tunnel', {'is_deleted':'false'})
        name = 'hermesaki-' + settings['domain']
        found = [t for t in tunnels if t['name'] == name]
        if len(found) > 1:
            raise CloudflareError('ambiguous_tunnel_name')
        tunnel = found[0] if found else None
        conflicts = []
        config = {'ingress':[{'service':'http_status:404'}]}
        if tunnel:
            if tunnel.get('config_src') != 'cloudflare':
                conflicts.append('Existing tunnel is locally managed; cannot safely change its routes.')
            else:
                config = self.call('GET',prefix+'/cfd_tunnel/'+tunnel['id']+'/configurations')['result']['config']
        if not isinstance(config.get('ingress'),list) or not config['ingress'] or config['ingress'][-1] != {'service':'http_status:404'}:
            conflicts.append('Tunnel must end with a deny-all fallback; existing fallback will not be overwritten.')
        actions = [{'kind':'tunnel','operation':'reuse' if tunnel else 'create','name':name,'id':tunnel['id'] if tunnel else None}]
        observed = {'zone':zone['id'], 'account':account, 'tunnel':{'id':tunnel['id'],'config':config} if tunnel else None, 'hosts':[]}
        operator_host,webmail_host=web_hosts(settings)
        for kind, hostname, origin in [('operator',operator_host,'http://api:8000'),('webmail',webmail_host,'http://webmail:80')]:
            if not hostname.endswith('.'+zone['name']):
                raise CloudflareError('web_hostname_must_belong_to_domain_zone')
            records = self.all('/zones/'+zone['id']+'/dns_records', {'name':hostname})
            matching = [a for a in apps if a.get('domain') == hostname]
            policies = self.all(prefix+'/access/apps/'+matching[0]['id']+'/policies') if len(matching)==1 else []
            compatible_app = len(matching)==1 and owner_policy(matching[0],policies,settings['owner_email'])
            if matching and not compatible_app:
                conflicts.append(hostname + ': existing Access policy differs; refusing to overwrite. Choose an unused setup domain, or review the Access application and restore the intended owner-only policy before refreshing.')
            target = tunnel['id']+'.cfargotunnel.com' if tunnel else '<new tunnel id>.cfargotunnel.com'
            compatible_dns = len(records)==1 and records[0].get('type')=='CNAME' and records[0].get('content','').rstrip('.')==target and records[0].get('proxied') is True
            if records and not compatible_dns:
                conflicts.append(hostname + ': existing DNS differs; refusing to overwrite. Choose an unused setup domain, or restore the intended proxied CNAME to '+target+' and refresh the plan.')
            route={'hostname':hostname,'service':origin}
            matching_routes=[r for r in config.get('ingress',[]) if r.get('hostname')==hostname]
            if matching_routes and matching_routes != [route]:
                conflicts.append(hostname + ': existing tunnel route differs; refusing to overwrite.')
            # Wildcards/path rules can shadow a new route. Do not infer compatibility.
            if any('*' in r.get('hostname','') for r in config.get('ingress',[])):
                conflicts.append('Existing wildcard tunnel routing needs operator review.')
            observed['hosts'].append({'hostname':hostname,'records':[{k:r.get(k) for k in ('id','type','content','proxied')} for r in records],
                'apps':[{k:a.get(k) for k in ('id','type','domain','aud')} for a in matching], 'policies':policies})
            actions.append({'kind':'access','operation':'reuse' if compatible_app else 'conflict' if matching else 'create','hostname':hostname,'allow_email':settings['owner_email'],'name':'Hermesaki '+kind})
            actions.append({'kind':'route','operation':'reuse' if matching_routes==[route] else 'conflict' if matching_routes else 'create',**route})
            actions.append({'kind':'dns','operation':'reuse' if compatible_dns else 'conflict' if records else 'create','hostname':hostname,'type':'CNAME','proxied':True,'target':target})
        plan = {'scope':'web_protection_only','zone_name':zone['name'],'zone_id':zone['id'],'account_id':account,'actions':actions,'conflicts':sorted(set(conflicts)),
            'apply_available':not conflicts,'checks':{'zone_read':'passed','dns_read':'passed','access_read':'passed','tunnel_read':'passed','write_permissions':'unverified'},
            'permission_preflight':{'resources':['Temporary TXT record','Disconnected Tunnel with deny-all route','Owner-only Access application without DNS'],'cleanup':'Remove every probe before provisioning the reviewed resources.','required':['Zone DNS Edit','Account Cloudflare Tunnel Edit','Account Access Apps and Policies Edit']},
            'remaining':['Mail deployment and connector startup remain separate.','Mail DNS, TLS, SMTP and end-to-end mail are not configured by this plan.']}
        plan['id'] = fingerprint({'settings':settings,'observed':observed,'actions':actions})
        return plan

    def verify_write_permissions(self, settings, approved, progress, checkpoint):
        """Probe only isolated resources, and finish cleanup before provisioning."""
        probe = progress.get('permission_probe')
        if probe and probe.get('state') == 'passed':
            return
        if probe and (probe.get('inflight') or probe.get('uncertain_write')):
            raise CloudflareError('uncertain_permission_probe_review_required')
        if probe and probe.get('state') == 'cleanup_required':
            while probe['resources']:
                path = probe['resources'][-1]['path']
                # DELETE is safely retryable, including an interrupted cleanup.
                try:
                    self.call('DELETE', path)
                except CloudflareError:
                    raise CloudflareError('permission_probe_cleanup_required') from None
                probe['resources'].pop()
                checkpoint(progress)
            probe['state'] = 'failed'
            checkpoint(progress)
        if not probe or probe.get('state') == 'failed':
            if probe and probe.get('resources'):
                raise CloudflareError('permission_probe_cleanup_required')
            probe = {'name':'hermesaki-check-'+secrets.token_hex(10), 'state':'checking', 'resources':[], 'checks':{}}
            progress['permission_probe'] = probe
            checkpoint(progress)
        account = '/accounts/' + approved['account_id']
        host = probe['name'] + '.' + approved['zone_name']
        def write(method, path, body=None):
            probe['inflight'] = {'method':method, 'path':path}
            checkpoint(progress)
            try:
                result = self.call(method, path, body)
            except CloudflareError as error:
                if str(error) == 'cloudflare_permission_denied':
                    probe.pop('inflight', None)
                    checkpoint(progress)
                raise
            probe.pop('inflight', None)
            return result
        def create(kind, path, body):
            result = write('POST', path, body)['result']
            probe['resources'].append({'kind':kind,'path':path+'/'+result['id']})
            probe['checks'][kind] = 'passed'
            checkpoint(progress)
            return path+'/'+result['id']
        failure = None
        try:
            create('dns', '/zones/'+approved['zone_id']+'/dns_records',
                   {'type':'TXT','name':host,'content':'Hermesaki permission check','ttl':60})
            tunnel = create('tunnel', account+'/cfd_tunnel', {'name':probe['name'],'config_src':'cloudflare'})
            write('PUT', tunnel+'/configurations', {'config':{'ingress':[{'service':'http_status:404'}]}})
            checkpoint(progress)
            create('access', account+'/access/apps', {'type':'self_hosted','name':probe['name'],'domain':host,
                   'session_duration':'15m','policies':[{'name':'Owner only','decision':'allow','precedence':1,
                   'include':[{'email':{'email':settings['owner_email']}}]}]})
        except CloudflareError as error:
            failure = error
        # An uncertain create must be reconciled by the operator before retrying.
        # Never lose its intent while cleaning up acknowledged resources.
        uncertain = probe.pop('inflight', None)
        try:
            while probe['resources']:
                resource = probe['resources'][-1]
                write('DELETE', resource['path'])
                probe['resources'].pop()
                checkpoint(progress)
        except CloudflareError:
            probe['state'] = 'cleanup_required'
            if uncertain: probe['uncertain_write'] = uncertain
            checkpoint(progress)
            raise CloudflareError('permission_probe_cleanup_required') from None
        if uncertain: probe['inflight'] = uncertain
        probe['state'] = 'failed' if failure else 'passed'
        checkpoint(progress)
        if failure:
            if str(failure) == 'cloudflare_permission_denied':
                raise CloudflareError('cloudflare_write_permission_required_dns_tunnel_access') from None
            raise failure

    def apply(self, settings, approved, progress, checkpoint):
        """Each acknowledged action is checkpointed. Ambiguous writes fail closed for review."""
        if not approved['apply_available'] or approved['conflicts']:
            raise CloudflareError('plan_has_conflicts')
        if not progress:
            if self.plan(settings)['id'] != approved['id']:
                raise CloudflareError('plan_changed_review_again')
            progress.update({'plan_id':approved['id'],'steps':{},'state':'applying'})
            checkpoint(progress)
        if progress['plan_id'] != approved['id']:
            raise CloudflareError('different_plan_in_progress')
        self.verify_write_permissions(settings, approved, progress, checkpoint)
        account, zone = approved['account_id'],approved['zone_id']
        prefix='/accounts/'+account
        steps=progress['steps']
        def step(key, run):
            if key in steps:return steps[key]
            # Persist intent first. A timeout/crash before receipt cannot silently retry a write.
            if progress.get('inflight'):
                raise CloudflareError('uncertain_cloudflare_write_review_required')
            progress['inflight']=key;checkpoint(progress)
            result=run()
            steps[key]=result;progress.pop('inflight',None);checkpoint(progress)
            return result
        action=approved['actions'][0]
        if action['operation']=='reuse':
            tunnel_id=action['id']
        else:
            tunnel_id=step('tunnel',lambda:self.call('POST',prefix+'/cfd_tunnel',{'name':action['name'],'config_src':'cloudflare'})['result']['id'])
        # Gate both hostnames before publishing any routing or DNS.
        for action in approved['actions']:
            if action['kind']!='access':continue
            host=action['hostname']
            if action['operation']=='create':
                step('access:'+host,lambda a=action:self.call('POST',prefix+'/access/apps',{'type':'self_hosted','name':a['name'],'domain':a['hostname'],'session_duration':'12h','policies':[{'name':'Owner only','decision':'allow','precedence':1,'include':[{'email':{'email':settings['owner_email']}}]}]})['result']['id'])
            # Check actual returned policy, including after resumption.
            found=[a for a in self.all(prefix+'/access/apps') if a.get('domain')==host]
            if len(found)!=1 or not owner_policy(found[0],self.all(prefix+'/access/apps/'+found[0]['id']+'/policies'),settings['owner_email']):
                raise CloudflareError('access_policy_verification_failed')
        path=prefix+'/cfd_tunnel/'+tunnel_id+'/configurations'
        def routes():
            config=copy.deepcopy(self.call('GET',path)['result'].get('config') or {'ingress':[{'service':'http_status:404'}]})
            if not config.get('ingress') or config['ingress'][-1]!={'service':'http_status:404'}:
                raise CloudflareError('tunnel_fallback_changed')
            for a in approved['actions']:
                if a['kind']!='route':continue
                rule={'hostname':a['hostname'],'service':a['service']}
                old=[r for r in config['ingress'] if r.get('hostname')==a['hostname']]
                if old and old!=[rule]:raise CloudflareError('tunnel_route_changed')
                if not old:config['ingress'].insert(-1,rule)
            self.call('PUT',path,{'config':config})
            return True
        step('routes',routes)
        for action in approved['actions']:
            if action['kind']!='dns' or action['operation']=='reuse':continue
            def dns(a=action):
                path='/zones/'+zone+'/dns_records'
                if self.all(path,{'name':a['hostname']}):raise CloudflareError('dns_changed_review_again')
                return self.call('POST',path,{'type':'CNAME','name':a['hostname'],'content':tunnel_id+'.cfargotunnel.com','proxied':True,'ttl':1})['result']['id']
            step('dns:'+action['hostname'],dns)
        # Verify final resources again, including reused DNS and resumed route steps.
        final = self.plan(settings)
        if final['conflicts'] or any(a['operation'] != 'reuse' for a in final['actions']):
            raise CloudflareError('post_apply_verification_failed')
        progress['state']='web_resources_applied';progress['tunnel_id']=tunnel_id;checkpoint(progress)
        return progress
