#!/usr/bin/env python3
import base64
import datetime
import json
import os
import secrets
import subprocess
from pathlib import Path
from volume_permissions import prepare_mail_volumes
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

os.chdir(Path(__file__).resolve().parents[1])
root = Path(".runtime")
root.mkdir(exist_ok=True, mode=0o700)
state = root / "product"
state.mkdir(exist_ok=True, mode=0o700)


def save(path, text):
    if not path.exists():
        path.write_text(text)
        path.chmod(0o600)


password = secrets.token_urlsafe(32)
if not (state / "management.json").exists():
    save(
        state / "management.json",
        json.dumps({"username": "admin", "password": password}),
    )
creds = json.loads((state / "management.json").read_text())
save(
    root / "bootstrap.env", "STALWART_RECOVERY_ADMIN=admin:" + creds["password"] + "\n"
)
save(state / "key", base64.b64encode(secrets.token_bytes(32)).decode())
save(
    state / "config.json",
    json.dumps(
        {
            "mode": "development",
            "domain": "example.test",
            "webhook_hosts": ["receiver"],
        },
        indent=2,
    ),
)
tls = state / "tls"
tls.mkdir(exist_ok=True)
if not (tls / "server.pem").exists():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.datetime.now(datetime.timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Hermesaki local")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("mail"), x509.DNSName("mail.example.test")]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    save(
        tls / "server.key",
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
    )
    save(tls / "server.pem", cert.public_bytes(serialization.Encoding.PEM).decode())
    save(tls / "ca.pem", cert.public_bytes(serialization.Encoding.PEM).decode())
    (tls / "ca.pem").chmod(0o644)


def dc(*args):
    subprocess.run(["docker", "compose", *args], check=True)


prepare_mail_volumes(root)
dc("build", "api")
dc("up", "-d", "mail", "capture")
dc("run", "--rm", "api", "python", "-m", "hermesaki.bootstrap", "initial")
dc("restart", "mail")
dc("run", "--rm", "api", "python", "-m", "hermesaki.bootstrap", "configure")
dc("restart", "mail")
dc("up", "-d", "api", "worker", "receiver", "webmail", "edge")
print(
    "API: http://localhost:19100  Webmail: http://localhost:19180  Capture: http://localhost:19125"
)
print(
    "Credentials are in .runtime/product. Run make credentials to display local login details."
)
