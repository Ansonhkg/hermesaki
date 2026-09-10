"""Development provisioning runs only on the isolated Compose network."""

import json
import os
import time
from pathlib import Path
from .mail import Stalwart
from .config import Config
from .store import Store
from .service import Service


def configure_container_logging(api):
    """Use the container log stream; never enable message/body debug tracing."""
    tracers = api.list("Tracer")
    if not any(t.get("@type") == "Stdout" and t.get("enable") for t in tracers):
        api.call("x:Tracer/set", {"create": {"console": {
            "@type": "Stdout", "enable": True, "level": "info", "ansi": False,
            "buffered": False,
        }}})
    defaults = {t["id"]: {"enable": False} for t in tracers
                if t.get("@type") == "Log" and t.get("path") == "/var/log/stalwart/"
                and t.get("enable")}
    if defaults:
        api.call("x:Tracer/set", {"update": defaults})


def run(phase):
    c = Config.load()
    production = c.mode == "production"
    if production and not os.environ.get("HERMESAKI_PROVISION"):
        raise RuntimeError(
            "production provisioning requires the explicit provision command"
        )
    root = Path(c.state)
    creds = json.loads((root / "management.json").read_text())
    api = Stalwart("http://mail:8080", creds["username"], creds["password"])
    for attempt in range(60):
        try:
            if phase == "initial":
                # A marker is persisted before the server is restarted.
                if (root / "bootstrapped").exists():
                    return
                result = api.call(
                    "x:Bootstrap/set",
                    {
                        "update": {
                            "singleton": {
                                "serverHostname": "mail." + c.domain,
                                "defaultDomain": c.domain,
                                "requestTlsCertificate": False,
                                "generateDkimKeys": production,
                            }
                        }
                    },
                )
                if production:
                    admin = result["updated"]["singleton"]
                    (root / "permanent-management.json").write_text(
                        json.dumps(
                            {"username": admin["username"], "password": admin["secret"]}
                        )
                    )
                (root / "bootstrapped").touch()
                return
            api.list("Domain")
            break
        except Exception:
            if attempt == 59:
                raise
            time.sleep(1)
    if phase == "configure":
        configure_container_logging(api)
        certificate = {
            "certificate": {
                "@type": "Text",
                "value": (root / "tls/server.pem").read_text(),
            },
            "privateKey": {
                "@type": "Text",
                "secret": (root / "tls/server.key").read_text(),
            },
        }
        if not (root / "certified").exists():
            api.call("x:Certificate/set", {"create": {"local": certificate}})
            (root / "certified").touch()
        if not production:
            api.ensure(
                "MtaRoute",
                "name",
                {
                    "@type": "Relay",
                    "name": "capture",
                    "address": "capture",
                    "port": 1025,
                    "implicitTls": False,
                    "allowInvalidCerts": False,
                    "protocol": "smtp",
                },
            )
        if not production:
            api.call(
                "x:MtaOutboundStrategy/set",
                {
                    "update": {
                        "singleton": {
                            "route": {
                                "else": "'capture'",
                                "match": {
                                    "0": {
                                        "if": "is_local_domain(rcpt_domain)",
                                        "then": "'local'",
                                    }
                                },
                            }
                        }
                    }
                },
            )
        s = Store(c.state)
        svc = Service(c, s, None, api)
        actor = {"id": "setup", "scopes": ["admin"]}
        if not (root / "operator-token").exists():
            (root / "operator-token").write_text(s.token(None, ["admin"])["token"])
        if production:
            (root / "management.json").write_text(
                (root / "permanent-management.json").read_text()
            )
            return
        users = []
        for local in ("alice", "bob"):
            account = svc.create_inbox(actor, local + "@" + c.domain)
            users.append(account)
            tokenfile = root / (local + "-token")
            if not tokenfile.exists():
                tokenfile.write_text(
                    s.token(account["id"], ["mail.read", "mail.write", "mail.delete"])[
                        "token"
                    ]
                )
        (root / "accounts.json").write_text(json.dumps(users))


if __name__ == "__main__":
    import sys

    run(sys.argv[1])
