#!/usr/bin/env python3
"""Explicit first-time setup on a new staging server. Never migrates an existing installation."""

import argparse
import base64
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from volume_permissions import prepare_mail_volumes

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hermesaki.config import Config

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--certificate", required=True)
ap.add_argument("--private-key", required=True)
ap.add_argument("--ca", required=True)
ap.add_argument("--tunnel-token-file", required=True)
args = ap.parse_args()
os.chdir(Path(__file__).resolve().parents[1])
c = Config(**json.loads(Path(args.config).read_text())).validate()
if c.mode != "production":
    raise SystemExit("production config required")
if (
    c.mail_host != "mail." + c.domain
    or c.management_url != "https://" + c.mail_host + ":443"
):
    raise SystemExit("mail_host and management_url must use mail.<domain>")
root = Path(".runtime")
state = root / "product"
if (root / "mail-etc/config.json").exists():
    raise SystemExit(
        "existing mail configuration found; use make deploy, never bootstrap over existing mail"
    )
root.mkdir(exist_ok=True, mode=0o700)
state.mkdir(exist_ok=True, mode=0o700)
(state / "tls").mkdir(exist_ok=True)


def put(path, value):
    path.write_text(value)
    path.chmod(0o600)


# Preparation is resumable before the mail server writes its configuration.
if not (state / "key").exists():
    put(state / "key", base64.b64encode(secrets.token_bytes(32)).decode())
if not (state / "management.json").exists():
    put(
        state / "management.json",
        json.dumps({"username": "admin", "password": secrets.token_urlsafe(32)}),
    )
put(Path(".env"), "HERMESAKI_MAIL_HOST=" + c.mail_host + "\n")
creds = json.loads((state / "management.json").read_text())
put(state / "config.json", json.dumps(c.__dict__))
put(root / "bootstrap.env", "STALWART_RECOVERY_ADMIN=admin:" + creds["password"] + "\n")
for source, target in [
    (args.certificate, state / "tls/server.pem"),
    (args.private_key, state / "tls/server.key"),
    (args.ca, state / "tls/ca.pem"),
    (args.tunnel_token_file, root / "tunnel-token"),
]:
    put(target, Path(source).read_text())
(state / "tls/ca.pem").chmod(0o644)
(root / "tunnel-token").chmod(0o644)
override = root / "bootstrap-compose.json"
put(
    override,
    json.dumps(
        {"services": {"mail": {"env_file": [str((root / "bootstrap.env").resolve())]}}}
    ),
)
cmd = ["docker", "compose", "-f", "compose.production.yaml", "-f", str(override)]


def run(*a):
    subprocess.run(cmd + list(a), check=True)


prepare_mail_volumes(root)
run("build", "api")
run("up", "-d", "mail")
run(
    "run",
    "--rm",
    "-e",
    "HERMESAKI_PROVISION=1",
    "api",
    "python",
    "-m",
    "hermesaki.bootstrap",
    "initial",
)
run("restart", "mail")
run(
    "run",
    "--rm",
    "-e",
    "HERMESAKI_PROVISION=1",
    "api",
    "python",
    "-m",
    "hermesaki.bootstrap",
    "configure",
)
subprocess.run(
    [
        "docker",
        "compose",
        "-f",
        "compose.production.yaml",
        "up",
        "-d",
        "--force-recreate",
        "mail",
    ],
    check=True,
)
(root / "bootstrap.env").unlink()
override.unlink()
(state / "permanent-management.json").unlink(missing_ok=True)
print(
    "Mail provisioned. Configure the tunnel routes and Access policies, then run make deploy. No HTTP port is published."
)
