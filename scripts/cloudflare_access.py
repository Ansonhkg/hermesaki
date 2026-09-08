#!/usr/bin/env python3
"""Plan or apply owner-only Access gates and tunnel routes. Credentials stay in env."""

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--apply", action="store_true")
args = ap.parse_args()
c = json.loads(Path(args.config).read_text())
required = [
    "account_id",
    "zone_id",
    "tunnel_id",
    "owner_email",
    "api_hostname",
    "inbox_hostname",
    "api_origin",
    "inbox_origin",
]
if any(not c.get(k) for k in required):
    raise SystemExit("missing configuration field")
plan = {
    "hosts": [c["api_hostname"], c["inbox_hostname"]],
    "allow": c["owner_email"],
    "tunnel_id": c["tunnel_id"],
}
if not args.apply:
    print(json.dumps(plan, indent=2))
    raise SystemExit(0)
token = os.environ["CLOUDFLARE_API_TOKEN"]


def call(method, path, body=None, query=None):
    url = "https://api.cloudflare.com/client/v4" + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.load(r)
    if not result.get("success"):
        raise RuntimeError("Cloudflare operation failed: " + path)
    return result["result"]


base = "/accounts/" + c["account_id"]
apps = call("GET", base + "/access/apps")
rules = []
for kind in ("api", "inbox"):
    host = c[kind + "_hostname"]
    existing = next((a for a in apps if a.get("domain") == host), None)
    if existing:
        policies = call("GET", base + "/access/apps/" + existing["id"] + "/policies")
        if (
            len(policies) != 1
            or policies[0].get("decision") != "allow"
            or policies[0].get("include") != [{"email": {"email": c["owner_email"]}}]
        ):
            raise RuntimeError(
                "existing Access policy differs; refusing to overwrite it"
            )
    else:
        existing = call(
            "POST",
            base + "/access/apps",
            {
                "type": "self_hosted",
                "name": "Hermesaki " + kind,
                "domain": host,
                "session_duration": "12h",
                "policies": [
                    {
                        "name": "Owner only",
                        "decision": "allow",
                        "precedence": 1,
                        "include": [{"email": {"email": c["owner_email"]}}],
                    }
                ],
            },
        )
    print(kind + " Access audience: " + existing["aud"])
    rules.append({"hostname": host, "service": c[kind + "_origin"]})
path = base + "/cfd_tunnel/" + c["tunnel_id"] + "/configurations"
config = call("GET", path)["config"]
for rule in rules:
    old = next(
        (r for r in config["ingress"] if r.get("hostname") == rule["hostname"]), None
    )
    if old and old != rule:
        raise RuntimeError("existing tunnel route differs")
    if not old:
        config["ingress"].insert(len(config["ingress"]) - 1, rule)
call("PUT", path, {"config": config})
for rule in rules:
    path = "/zones/" + c["zone_id"] + "/dns_records"
    records = call("GET", path, query={"name": rule["hostname"]})
    content = c["tunnel_id"] + ".cfargotunnel.com"
    if records:
        if (
            len(records) != 1
            or records[0]["type"] != "CNAME"
            or records[0]["content"] != content
            or not records[0]["proxied"]
        ):
            raise RuntimeError("existing DNS record differs")
    else:
        call(
            "POST",
            path,
            {
                "type": "CNAME",
                "name": rule["hostname"],
                "content": content,
                "proxied": True,
                "ttl": 1,
            },
        )
print("Access gates, tunnel routes and proxied DNS are configured.")
