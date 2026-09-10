"""Apply renewed certificates over the internal management network and verify the served leaf."""
import hashlib
import json
import os
import socket
import ssl
import time
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from .config import Config
from .mail import Stalwart
from .setup_services import private_write


def sync(config, certificate, key, hostname=None):
    root=Path(config.state)
    pem=Path(certificate).read_text();private=Path(key).read_text()
    extra=hostname is not None
    hostname=hostname or config.mail_host
    leaf=x509.load_pem_x509_certificate(pem.encode())
    names=leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
    if hostname not in names:raise ValueError('certificate_hostname_mismatch')
    connection_host='mail' if extra else config.mail_host
    expected=hashlib.sha256(x509.load_pem_x509_certificate(pem.encode()).public_bytes(serialization.Encoding.DER)).hexdigest()
    marker=root/('certificate-current-'+hashlib.sha256(hostname.encode()).hexdigest()[:16] if extra else 'certificate-current')
    if marker.exists() and marker.read_text()==expected:
        with socket.create_connection((connection_host,config.mail_port),timeout=5) as connection:
            with ssl.create_default_context(cafile=config.ca_file).wrap_socket(connection,server_hostname=hostname) as secured:
                if hashlib.sha256(secured.getpeercert(binary_form=True)).hexdigest()==expected:return False
    creds=json.loads((root/'management.json').read_text())
    # This endpoint has no host-published port and lives on the private Docker network.
    api=Stalwart(config.management_url if extra else 'http://mail:8080',creds['username'],creds['password'])
    rows=[r for r in api.list('Certificate') if hostname in r.get('subjectAlternativeNames',[])]
    value={'certificate':{'@type':'Text','value':pem},'privateKey':{'@type':'Text','secret':private}}
    if not rows and extra:
        api.call('x:Certificate/set',{'create':{'managed':value}})
    elif len(rows)==1:
        api.call('x:Certificate/set',{'update':{rows[0]['id']:value}})
    else:raise RuntimeError('certificate_identity_ambiguous')
    api.call('x:Action/set',{'create':{'reload':{'@type':'ReloadTlsCertificates'}}})
    context=ssl.create_default_context(cafile=config.ca_file)
    for attempt in range(30):
        with socket.create_connection((connection_host,config.mail_port),timeout=5) as connection:
            with context.wrap_socket(connection,server_hostname=hostname) as secured:
                actual=hashlib.sha256(secured.getpeercert(binary_form=True)).hexdigest()
        if actual==expected:
            private_write(marker,expected)
            if not extra:
                private_write(root/'tls/server.pem',pem);private_write(root/'tls/server.key',private)
            return True
        time.sleep(1)
    raise RuntimeError('renewed_certificate_not_served')


def main():
    config=Config.load()
    hostname=os.environ.get('HERMESAKI_CERTIFICATE_HOST')
    health=Path(config.state)/('certificate-health-'+hashlib.sha256(hostname.encode()).hexdigest()[:16]+'.json' if hostname else 'certificate-health.json')
    while True:
        try:
            changed=sync(config,os.environ.get('HERMESAKI_CERTIFICATE_FILE','/certificates/live/hermesaki/fullchain.pem'),os.environ.get('HERMESAKI_CERTIFICATE_KEY','/certificates/live/hermesaki/privkey.pem'),os.environ.get('HERMESAKI_CERTIFICATE_HOST'))
            private_write(health,json.dumps({'status':'verified','checked_at':int(time.time()),'changed':changed}))
        except Exception:
            private_write(health,json.dumps({'status':'failed','checked_at':int(time.time()),'error':'certificate_sync_failed'}))
        time.sleep(60)

if __name__=='__main__':main()
