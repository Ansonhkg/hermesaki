"""Real disposable mail bootstrap; fake provider/certificate, no network egress.
This verifies the runtime, not public-cloud acceptance. Never sends external mail.
"""
import datetime
import json
import secrets
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from hermesaki.setup_services import Services, private_write
from hermesaki.setup_runtime import Runtime
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

repo=Path(__file__).resolve().parents[1]
name='runtime-'+secrets.token_hex(4)
services=Services(repo/'.runtime'/name)
settings={'domain':name+'.example.com','server_ip':'127.0.0.1','owner_email':'owner@example.com'}
plan={'id':name,'account_id':'fixture','tunnel_id':'fixture','options':{'access_team':'fixture'},'first_mailbox':'hi@'+settings['domain']}
class Provider:
    token='local-fixture-not-a-credential'
    def plan(self,settings):return {'conflicts':[],'actions':[{'operation':'reuse'}]}
    def all(self,path):return [{'domain':'hermesaki.'+settings['domain'],'aud':'fixture'}]
    def call(self,*args):return {'result':'local-fixture-no-connector'}
class Local(Runtime):
    def compose(self,settings):
        value=super().compose(settings)
        # All runtime services use one internal Docker network. No published ports.
        value['networks']={'private':{'internal':True}}
        [value['services'].pop(n) for n in ('tunnel','certificate_sync','certificate_renewal')]
        for key,service in value['services'].items():
            service.pop('ports',None)
            service['networks']={'private':{'aliases':['mail.'+settings['domain']]}} if key=='mail' else ['private']
            if key in ('api','worker'):
                service['image']='hermesaki-setup-api:test';service.pop('build',None)
        return value
    def dc(self,*args,**kwargs):
        if args==('build','api'):return ''
        if 'tunnel' in args:args=tuple(x for x in args if x not in ('tunnel','certificate_sync','certificate_renewal'))
        return super().dc(*args,**kwargs)
    def certificate(self,settings):
        tls=self.root/'product/tls'
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        now=datetime.datetime.now(datetime.timezone.utc)
        subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Local test only')])
        cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True,path_length=None),True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('mail.'+settings['domain'])]),False).sign(key,hashes.SHA256()))
        private_write(tls/'server.key',key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode())
        pem=cert.public_bytes(serialization.Encoding.PEM).decode()
        private_write(tls/'server.pem',pem);private_write(tls/'ca.pem',pem);(tls/'ca.pem').chmod(0o644)

runtime=Local(services);progress={}
def checkpoint(value):
    private_write(services.directory/'progress.json',json.dumps(value))
    print(json.dumps({'state':value.get('state'),'stage':value.get('stage'),'steps':value.get('steps')}),flush=True)
try:
    runtime.apply(settings,plan,progress,checkpoint,Provider())
    first=runtime.dc('run','--rm','-T','api','python','-c',"from hermesaki.http import create_app; from pathlib import Path; import json; a=create_app();m=json.loads(Path('/state/first-mailbox.json').read_text());print(json.dumps({'mailbox':m['email'],'folders':a.s.mail.folders(a.s.store.inbox(m['id']))}))")
    print(first,flush=True)
    print(runtime.dc('run','--rm','-T','api','python','/app/tests/runtime_certificates.py'),flush=True)
    runtime.apply(settings,plan,progress,checkpoint,Provider())
    assert not (runtime.root/'bootstrap.env').exists()
    print('PASS: real isolated mail bootstrap, verified mailbox login, scoped runtime storage, idempotent retry. Public deployment remains unverified.',flush=True)
finally:
    if (runtime.root/'compose.json').exists():runtime.dc('down')
