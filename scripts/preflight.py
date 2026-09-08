#!/usr/bin/env python3
"""Fail closed on missing production prerequisites. Does not alter DNS."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hermesaki.config import Config

root = Path(".runtime")
c = Config(**json.loads((root / "product/config.json").read_text())).validate()
if c.mode != "production":
    raise SystemExit("production config required")
for f in [
    "product/key",
    "product/management.json",
    "product/tls/ca.pem",
    "mail-etc/config.json",
    "tunnel-token",
]:
    if not (root / f).is_file():
        raise SystemExit("missing " + f)
for typ, name in [("MX", c.domain), ("TXT", c.domain), ("TXT", "_dmarc." + c.domain)]:
    result = subprocess.check_output(["dig", "+short", typ, name], text=True).strip()
    if not result:
        raise SystemExit("missing DNS " + typ + " " + name)
print(
    "Local production prerequisites present. External Access policy, DKIM, PTR and SMTP connectivity still require staging verification."
)
