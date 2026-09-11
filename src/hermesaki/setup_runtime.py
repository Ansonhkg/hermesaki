"""Owned fresh-install runtime. Invoked only after exact plan authorization."""
import base64
import json
import os
import secrets
import ssl
import subprocess
from pathlib import Path
from .setup_services import DeploymentError, private_write
from .config import Config
from .setup_cloudflare import web_hosts


class Runtime:
    def __init__(self, services):
        self.services=services
        self.root=services.root
        self.repo=services.repository
        self.lock=json.loads((self.repo/'components.lock.json').read_text())

    def run(self, args, stdin=None):
        try:
            result=subprocess.run(args,input=stdin,text=True,capture_output=True,timeout=900,check=True,cwd=self.repo)
        except (OSError,subprocess.SubprocessError):
            # Provider/process errors can contain credentials. Only a stable stage error leaves this class.
            raise DeploymentError('runtime_command_failed_inspect_private_host') from None
        return result.stdout

    def dc(self,*args,bootstrap=False,stdin=None):
        cmd=['docker','compose','-f',str(self.root/'compose.json')]
        if bootstrap:cmd+=['-f',str(self.root/'bootstrap-compose.json')]
        return self.run(cmd+list(args),stdin)

    def prepare(self,settings,plan,provider):
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        marker=self.root/'owned-plan'
        if marker.exists() and marker.read_text()!=plan['id']:
            raise DeploymentError('installation_owned_by_different_plan')
        if not marker.exists() and any(self.root.iterdir()):
            raise DeploymentError('existing_installation_not_owned')
        private_write(marker,plan['id'])
        state=self.root/'product';state.mkdir(exist_ok=True,mode=0o700)
        (state/'tls').mkdir(exist_ok=True,mode=0o700)
        for name in ('mail-etc','mail-data','roundcube','acme'):(self.root/name).mkdir(exist_ok=True,mode=0o700)
        for name,value in [('key',base64.b64encode(secrets.token_bytes(32)).decode()),('management.json',json.dumps({'username':'admin','password':secrets.token_urlsafe(32)}))]:
            if not (state/name).exists():private_write(state/name,value)
        account='/accounts/'+plan['account_id']
        apps=provider.all(account+'/access/apps')
        apps=[a for a in apps if a.get('domain')==web_hosts(settings)[0]]
        if len(apps)!=1 or not apps[0].get('aud'):raise DeploymentError('operator_access_audience_required')
        c=Config(mode='production',domain=settings['domain'],mail_host='mail.'+settings['domain'],management_url='https://mail.'+settings['domain']+':443',
                 public_url='https://'+web_hosts(settings)[0],webmail_url='https://'+web_hosts(settings)[1],access_team=plan['options']['access_team'],access_aud=apps[0]['aud'])
        c.validate();private_write(state/'config.json',json.dumps(c.__dict__))
        token=provider.call('GET',account+'/cfd_tunnel/'+plan['tunnel_id']+'/token')['result']
        private_write(self.root/'tunnel-token',token)
        # Non-root cloudflared reads the file inside a private 0700 host directory.
        (self.root/'tunnel-token').chmod(0o644)
        creds=json.loads((state/'management.json').read_text())
        private_write(self.root/'bootstrap.env','STALWART_RECOVERY_ADMIN=admin:'+creds['password']+'\n')
        private_write(self.root/'bootstrap-compose.json',json.dumps({'services':{'mail':{'env_file':[str(self.root/'bootstrap.env')]}}}))
        private_write(self.root/'certbot-secret/cloudflare.ini','dns_cloudflare_api_token = '+provider.token+'\n')
        private_write(self.root/'compose.json',json.dumps(self.compose(settings),indent=2))

    def compose(self,settings):
        root=str(self.root);host='mail.'+settings['domain'];image='hermesaki-fresh-'+settings['domain'].replace('.','-')
        base={'image':image,'volumes':[root+'/product:/state'],'networks':['private','delivery'],'restart':'unless-stopped'}
        return {'name':image,'services':{
            'mail':{'image':self.lock['stalwart']['image'],'ports':[{'target':25,'published':'25','host_ip':settings['server_ip']}],
                    'volumes':[root+'/mail-etc:/etc/stalwart',root+'/mail-data:/var/lib/stalwart'],
                    'networks':{'private':{'aliases':[host]},'delivery':{}},'restart':'unless-stopped'},
            'api':{**base,'build':{'context':str(self.repo),'dockerfile':'docker/api/Dockerfile'}},
            'worker':{**base,'command':['python','-m','hermesaki.worker']},
            'certificate_sync':{**base,'command':['python','-m','hermesaki.tls_sync'],'volumes':base['volumes']+[root+'/acme:/certificates:ro'],'networks':['private']},
            'certificate_renewal':{'image':self.lock['certbot']['image'],'entrypoint':['/bin/sh','-c'],
                'command':['while true; do certbot renew --non-interactive; sleep 43200; done'],
                'volumes':[root+'/acme:/etc/letsencrypt',root+'/certbot-secret:/run/hermesaki-certbot:ro'],
                'networks':['delivery'],'restart':'unless-stopped'},
            'webmail':{'image':self.lock['roundcube']['image'],'environment':{'ROUNDCUBEMAIL_DEFAULT_HOST':'ssl://'+host,'ROUNDCUBEMAIL_DEFAULT_PORT':'993','ROUNDCUBEMAIL_SMTP_SERVER':'ssl://'+host,'ROUNDCUBEMAIL_SMTP_PORT':'465','ROUNDCUBEMAIL_PLUGINS':'archive,zipdownload'},
                'volumes':[root+'/roundcube:/var/roundcube/db',root+'/product/tls/ca.pem:/etc/hermesaki/ca.pem:ro',str(self.repo/'docker/roundcube/local.inc.php')+':/var/roundcube/config/local.inc.php:ro'],
                'networks':['private'],'restart':'unless-stopped'},
            'tunnel':{'image':self.lock['cloudflared']['image'],'command':['tunnel','--no-autoupdate','run','--token-file','/run/secrets/tunnel'],
                'volumes':[root+'/tunnel-token:/run/secrets/tunnel:ro'],'networks':['private','delivery'],'restart':'unless-stopped'}},
            'networks':{'private':{'internal':True},'delivery':{}}}

    def certificate(self,settings):
        self.run(['docker','run','--rm','-v',str(self.root/'acme')+':/etc/letsencrypt','-v',str(self.root/'certbot-secret')+':/run/hermesaki-certbot:ro',
            self.lock['certbot']['image'],'certonly','--non-interactive','--agree-tos','--dns-cloudflare','--dns-cloudflare-credentials','/run/hermesaki-certbot/cloudflare.ini',
            '--dns-cloudflare-propagation-seconds','30','--email',settings['owner_email'],'--cert-name','hermesaki','-d','mail.'+settings['domain']])
        live=self.root/'acme/live/hermesaki';tls=self.root/'product/tls'
        private_write(tls/'server.pem',(live/'fullchain.pem').read_text())
        private_write(tls/'server.key',(live/'privkey.pem').read_text())
        ca=ssl.get_default_verify_paths().cafile
        if not ca:raise DeploymentError('system_ca_bundle_required')
        private_write(tls/'ca.pem',Path(ca).read_text());(tls/'ca.pem').chmod(0o644)

    def apply(self,settings,plan,progress,checkpoint,provider):
        def step(name,action):
            if name in progress.get('steps',[]):return
            progress['stage']=name;checkpoint(progress)
            action()
            progress.setdefault('steps',[]).append(name);checkpoint(progress)
        step('prepare',lambda:self.prepare(settings,plan,provider))
        step('certificate',lambda:self.certificate(settings))
        step('build',lambda:self.dc('build','api'))
        def permissions():
            self.run(['docker','run','--rm','--network','none','--user','0:0','-v',str(self.root)+':/state',self.lock['python']['image'],'python','-c',
                "import os; [os.chown('/state/'+n,2000,2000) for n in ('mail-data','mail-etc')]"])
        step('permissions',permissions)
        step('start_mail',lambda:self.dc('up','-d','mail',bootstrap=True))
        step('bootstrap',lambda:self.dc('run','--rm','-e','HERMESAKI_PROVISION=1','api','python','-m','hermesaki.bootstrap','initial',bootstrap=True))
        step('restart_mail',lambda:self.dc('restart','mail',bootstrap=True))
        step('configure',lambda:self.dc('run','--rm','-e','HERMESAKI_PROVISION=1','api','python','-m','hermesaki.bootstrap','configure',bootstrap=True))
        step('retire_recovery',lambda:self.dc('up','-d','--force-recreate','mail'))
        def mailbox():
            script='''import json
from pathlib import Path
from hermesaki.http import create_app
app=create_app();s=app.s.store
actor=s.auth(Path('/state/operator-token').read_text())
account=app.s.create_inbox(actor,ADDRESS)
app.s.mail.verify_credentials(account['email'],s.open(s.inbox(account['id'])['secret'],account['id']))
Path('/state/first-mailbox.json').write_text(json.dumps(account))
'''.replace('ADDRESS',repr(plan['first_mailbox']))
            self.dc('run','--rm','-T','api','python','-',stdin=script)
        step('first_mailbox',mailbox)
        def start_services():
            current=provider.plan(settings)
            if current['conflicts'] or any(a['operation']!='reuse' for a in current['actions']):
                raise DeploymentError('web_protection_changed_before_exposure')
            self.dc('up','-d','api','worker','webmail','tunnel','certificate_sync','certificate_renewal')
        step('start_services',start_services)
        for name in ('bootstrap.env','bootstrap-compose.json','product/permanent-management.json'):(self.root/name).unlink(missing_ok=True)
        progress.pop('error',None)
        progress.update(state='services_running',stage='verify_mail_and_access',complete=False);checkpoint(progress)
        return progress
