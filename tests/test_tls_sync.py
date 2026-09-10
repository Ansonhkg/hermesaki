import datetime,tempfile,unittest,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from hermesaki.tls_sync import sync

class CertificateSync(unittest.TestCase):
 def test_additional_hostname_preserves_primary_and_rejects_wrong_certificate(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'tls').mkdir();(root/'tls/server.pem').write_text('primary-certificate');(root/'management.json').write_text(json.dumps({'username':'fixture','password':'fixture'}))
   key=rsa.generate_private_key(public_exponent=65537,key_size=2048);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'mail.example.com')]);now=datetime.datetime.now(datetime.timezone.utc)
   cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1).not_valid_before(now).not_valid_after(now+datetime.timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('mail.example.com')]),critical=False).sign(key,hashes.SHA256())
   (root/'new.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM));(root/'new.key').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
   config=SimpleNamespace(state=directory,mail_host='primary.example.com',mail_port=993,ca_file=None,management_url='https://primary.example.com')
   with patch('hermesaki.tls_sync.Stalwart') as api,patch('hermesaki.tls_sync.socket.create_connection'),patch('hermesaki.tls_sync.ssl.create_default_context') as context:
    with self.assertRaises(ValueError):sync(config,root/'new.pem',root/'new.key','wrong.example.com')
    api.assert_not_called()
    api.return_value.list.return_value=[{'id':'primary','subjectAlternativeNames':{'primary.example.com':True}}]
    context.return_value.wrap_socket.return_value.__enter__.return_value.getpeercert.return_value=cert.public_bytes(serialization.Encoding.DER)
    self.assertTrue(sync(config,root/'new.pem',root/'new.key','mail.example.com'))
    self.assertIn('create',api.return_value.call.call_args_list[0].args[1])
    self.assertEqual((root/'tls/server.pem').read_text(),'primary-certificate')
    self.assertFalse(sync(config,root/'new.pem',root/'new.key','mail.example.com'))
