"""Apply renewed certificates over the internal management network and verify the served leaf."""
import hashlib
import json
import socket
import ssl
import time
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from .config import Config
from .mail import Stalwart
from .setup_services import private_write


def sync(config, certificate, key):
    root=Path(config.state)
    pem=Path(certificate).read_text();private=Path(key).read_text()
    expected=hashlib.sha256(x509.load_pem_x509_certificate(pem.encode()).public_bytes(serialization.Encoding.DER)).hexdigest()
    marker=root/'certificate-current'
    if marker.exists() and marker.read_text()==expected:
        with socket.create_connection((config.mail_host,config.mail_port),timeout=5) as connection:
            with ssl.create_default_context(cafile=config.ca_file).wrap_socket(connection,server_hostname=config.mail_host) as secured:
                if hashlib.sha256(secured.getpeercert(binary_form=True)).hexdigest()==expected:return False
    creds=json.loads((root/'management.json').read_text())
    # This endpoint has no host-published port and lives on the private Docker network.
    api=Stalwart('http://mail:8080',creds['username'],creds['password'])
    rows=[r for r in api.list('Certificate') if config.mail_host in r.get('subjectAlternativeNames',[])]
    if len(rows)!=1:raise RuntimeError('certificate_identity_ambiguous')
    api.call('x:Certificate/set',{'update':{rows[0]['id']:{'certificate':{'@type':'Text','value':pem},'privateKey':{'@type':'Text','secret':private}}}})
    api.call('x:Action/set',{'create':{'reload':{'@type':'ReloadTlsCertificates'}}})
    context=ssl.create_default_context(cafile=config.ca_file)
    for attempt in range(30):
        with socket.create_connection((config.mail_host,config.mail_port),timeout=5) as connection:
            with context.wrap_socket(connection,server_hostname=config.mail_host) as secured:
                actual=hashlib.sha256(secured.getpeercert(binary_form=True)).hexdigest()
        if actual==expected:
            private_write(marker,expected)
            private_write(root/'tls/server.pem',pem);private_write(root/'tls/server.key',private)
            return True
        time.sleep(1)
    raise RuntimeError('renewed_certificate_not_served')


def main():
    config=Config.load()
    while True:
        try:
            changed=sync(config,'/certificates/live/hermesaki/fullchain.pem','/certificates/live/hermesaki/privkey.pem')
            private_write(Path(config.state)/'certificate-health.json',json.dumps({'status':'verified','checked_at':int(time.time()),'changed':changed}))
        except Exception:
            private_write(Path(config.state)/'certificate-health.json',json.dumps({'status':'failed','checked_at':int(time.time()),'error':'certificate_sync_failed'}))
        time.sleep(60)

if __name__=='__main__':main()
