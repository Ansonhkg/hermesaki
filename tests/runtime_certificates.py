"""Real certificate replacement and public DKIM export on a disposable runtime only."""
import datetime
import json
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID
from hermesaki.http import create_app
from hermesaki.setup_dkim import public_records
from hermesaki.tls_sync import sync

app=create_app()
assert app.c.domain.startswith('runtime-') and app.c.domain.endswith('.example.com')
root=Path('/state/tls')
ca=x509.load_pem_x509_certificate((root/'ca.pem').read_bytes())
key=serialization.load_pem_private_key((root/'server.key').read_bytes(),None)
now=datetime.datetime.now(datetime.timezone.utc)
cert=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Renewed fixture leaf')]))
      .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
      .not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(hours=12))
      .add_extension(x509.SubjectAlternativeName([x509.DNSName(app.c.mail_host)]),False).sign(key,hashes.SHA256()))
(root/'renewed.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
records=public_records(app.s.provision,app.c.domain)
assert len(records)==2 and all('PRIVATE' not in json.dumps(r) for r in records)
assert sync(app.c,root/'renewed.pem',root/'server.key')
assert not sync(app.c,root/'renewed.pem',root/'server.key')
print(json.dumps({'public_dkim_records':len(records),'renewed_certificate_served':True,'repeat_sync_unchanged':True}))
