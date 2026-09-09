"""Private first-run control plane; does not expose or provision mail yet."""
import argparse
import fcntl
from contextlib import contextmanager
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import sqlite3
from pathlib import Path
from .setup_cloudflare import Cloudflare, CloudflareError
from .setup_preflight import host_checks
from wsgiref.simple_server import make_server, WSGIRequestHandler


class Rejected(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Setup:
    def __init__(self, directory, cloudflare=Cloudflare):
        self.cloudflare = cloudflare
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self.database = self.directory / "setup.sqlite"
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS preflight (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS progress (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS plans (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), bootstrap TEXT NOT NULL, owner TEXT, settings TEXT)")
            if not db.execute("SELECT 1 FROM state").fetchone():
                raw = secrets.token_urlsafe(32)
                # Transaction serializes competing first starts. Token is only a local file.
                db.execute("INSERT INTO state VALUES(1,?,NULL,NULL)", (digest(raw),))
                token_file = self.directory / "bootstrap-token"
                fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w") as f:
                    f.write(raw)
        self.database.chmod(0o600)

    @contextmanager
    def connect(self):
        fd = os.open(self.directory / "setup.lock", os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            db = sqlite3.connect(self.database, timeout=15)
            db.row_factory = sqlite3.Row
            try:
                db.execute("BEGIN IMMEDIATE")
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

    def call(self, method, path, token, data):
        with self.connect() as db:
            row = db.execute("SELECT * FROM state WHERE id=1").fetchone()
            if method == "GET" and path == "/v1/setup/status":
                return {"claimed": bool(row["owner"]), "api_version": "1", "next_action": "authenticate" if row["owner"] else "claim"}
            if method == "POST" and path == "/v1/setup/claim":
                if row["owner"]:
                    raise Rejected(409, "owner_already_claimed")
                if not token or not hmac.compare_digest(digest(token), row["bootstrap"]):
                    raise Rejected(401, "bootstrap_required")
                owner = data.get("owner_token", "")
                # Supplied by client so a lost HTTP response cannot lose the owner credential.
                if not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", owner) or owner == token:
                    raise Rejected(400, "generate_a_new_owner_token_with_32_random_bytes")
                db.execute("UPDATE state SET owner=?,bootstrap='' WHERE id=1", (digest(owner),))
                db.commit()
                (self.directory / "bootstrap-token").unlink(missing_ok=True)
                return {"claimed": True, "next_action": "configure"}
            if not row["owner"] or not token or not hmac.compare_digest(digest(token), row["owner"]):
                raise Rejected(401, "owner_required")
            if method == "POST" and path == "/v1/setup/preflight":
                if not row["settings"]:
                    raise Rejected(409, "configuration_required")
                result = host_checks(json.loads(row["settings"]))
                db.execute("INSERT OR REPLACE INTO preflight VALUES(1,?)", (json.dumps(result),))
                return result
            if method == "POST" and path == "/v1/setup/apply":
                saved = db.execute("SELECT value FROM plans WHERE id=1").fetchone()
                if not saved:
                    raise Rejected(409, "plan_required")
                plan = json.loads(saved["value"])
                if data != {"confirm_plan_id": plan["id"]}:
                    raise Rejected(400, "exact_plan_confirmation_required")
                current = db.execute("SELECT value FROM progress WHERE id=1").fetchone()
                progress = json.loads(current["value"]) if current else {}
                def checkpoint(value):
                    db.execute("INSERT OR REPLACE INTO progress VALUES(1,?)", (json.dumps(value),))
                    db.commit()
                try:
                    result = self.cloudflare((self.directory / "cloudflare-token").read_text()).apply(json.loads(row["settings"]), plan, progress, checkpoint)
                except CloudflareError as error:
                    raise Rejected(409, str(error))
                return {"progress":result, "complete":False, "next_action":"deploy_private_services_and_verify"}
            if method == "PUT" and path == "/v1/setup/cloudflare":
                raw = data.get("token")
                if set(data) != {"token"} or not isinstance(raw, str) or not 20 <= len(raw) <= 512 or not raw.isascii() or any(c.isspace() for c in raw):
                    raise Rejected(400, "invalid_cloudflare_token")
                if not row["settings"]:
                    raise Rejected(409, "configuration_required")
                try:
                    plan = self.cloudflare(raw).plan(json.loads(row["settings"]))
                except CloudflareError as error:
                    raise Rejected(400, str(error))
                # No credential is saved until validation succeeds. Atomic replacement supports rotation.
                file = self.directory / "cloudflare-token"
                temporary = self.directory / "cloudflare-token.new"
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w") as stream:
                    stream.write(raw)
                temporary.chmod(0o600)
                os.replace(temporary, file)
                if db.execute("SELECT 1 FROM progress").fetchone():
                    saved = db.execute("SELECT value FROM plans WHERE id=1").fetchone()
                    plan = json.loads(saved["value"])
                else:
                    db.execute("INSERT OR REPLACE INTO plans VALUES(1,?)", (json.dumps(plan),))
                return {"credential_saved": True, "plan": plan}
            if method == "POST" and path == "/v1/setup/plan":
                if db.execute("SELECT 1 FROM progress").fetchone():
                    raise Rejected(409, "provisioning_started_cannot_replace_plan")
                if not row["settings"]:
                    raise Rejected(409, "configuration_required")
                file = self.directory / "cloudflare-token"
                if not file.exists():
                    raise Rejected(409, "cloudflare_credential_required")
                try:
                    plan = self.cloudflare(file.read_text()).plan(json.loads(row["settings"]))
                except CloudflareError as error:
                    raise Rejected(400, str(error))
                db.execute("INSERT OR REPLACE INTO plans VALUES(1,?)", (json.dumps(plan),))
                return plan
            if method == "PUT" and path == "/v1/setup/configuration":
                settings = validate(data)
                if db.execute("SELECT 1 FROM progress").fetchone():
                    raise Rejected(409, "provisioning_started_cannot_replace_configuration")
                db.execute("UPDATE state SET settings=? WHERE id=1", (json.dumps(settings),))
                db.execute("DELETE FROM plans")
                db.execute("DELETE FROM preflight")
                return self.next_actions(self.snapshot(settings))
            if method == "GET" and path == "/v1/setup":
                result = self.snapshot(json.loads(row["settings"]) if row["settings"] else None)
                plan = db.execute("SELECT value FROM plans WHERE id=1").fetchone()
                result["cloudflare_plan"] = json.loads(plan["value"]) if plan else None
                progress = db.execute("SELECT value FROM progress WHERE id=1").fetchone()
                result["provisioning"] = json.loads(progress["value"]) if progress else None
                preflight = db.execute("SELECT value FROM preflight WHERE id=1").fetchone()
                result["host_preflight"] = json.loads(preflight["value"]) if preflight else None
                return self.next_actions(result)
            raise Rejected(404, "not_found")

    def next_actions(self, result):
        plan, progress = result.get("cloudflare_plan"), result.get("provisioning")
        checks = {item["id"]: item for item in result["checks"]}
        result["operations"] = [{"method":"GET", "path":"/v1/setup"}]
        result["validation_failures"] = []
        if not result["settings"]:
            action, method, path = "configure", "PUT", "/v1/setup/configuration"
        elif not plan:
            action, method, path = "connect_cloudflare", "PUT", "/v1/setup/cloudflare"
        else:
            checks["cloudflare_permissions"].update(state="partial", detail="Read access verified; writes require apply.")
            result["operations"].append({"method":"PUT", "path":"/v1/setup/cloudflare"})
            if progress and progress.get("inflight"):
                action, method, path = "review_uncertain_operation", None, None
                result["state"] = "needs_review"
                result["validation_failures"] = [{"code":"uncertain_cloudflare_write", "operation":progress["inflight"]}]
            elif progress and progress.get("state") == "web_resources_applied":
                action, method, path = "deploy_private_services_and_verify", None, None
                result["state"] = "web_resources_applied"
                for name in ("dns", "tunnel", "access"):
                    checks[name].update(state="configured", detail="Remote web resources checked; running services and edge access still require verification.")
            elif plan["conflicts"]:
                action, method, path = "resolve_conflicts_and_refresh", "POST", "/v1/setup/plan"
                result["state"] = "blocked"
                result["validation_failures"] = [{"code":"resource_conflict", "detail":text} for text in plan["conflicts"]]
            else:
                action, method, path = "review_and_apply_plan", "POST", "/v1/setup/apply"
                result["state"] = "plan_ready"
        if result["settings"]:
            result["operations"].append({"method":"POST", "path":"/v1/setup/preflight"})
        result["next_action"] = action
        if path:
            result["operations"].append({"method":method, "path":path})
        result["missing_prerequisites"] = [check["id"] for check in result["checks"] if check["state"] == "pending"]
        return result

    def snapshot(self, settings):
        pending = ["cloudflare_permissions", "dns", "tunnel", "access", "origin_protection", "smtp", "reverse_dns", "tls", "external_mail"]
        result = {"state": "configuration_saved" if settings else "configuration_required", "complete": False,
                  "settings": settings, "next_action": "verify_infrastructure" if settings else "configure",
                  "checks": [{"id": x, "state": "pending"} for x in pending],
                  "operations": [{"method": "GET", "path": "/v1/setup"}, {"method": "PUT", "path": "/v1/setup/configuration"}],
                  "limitations": ["Cloudflare web provisioning is available. Mail-service deployment and end-to-end verification remain incomplete."]}
        if settings:
            result["plan"] = {"state": "draft", "changes_applied": False, "domain": settings["domain"],
                "mail_hostname": "mail." + settings["domain"],
                "webmail_hostname": "inbox." + settings["domain"],
                "operator_hostname": "hermesaki." + settings["domain"],
                "preserve_existing_resources": True}
        return result


def validate(data):
    if set(data) != {"domain", "server_ip", "owner_email"}:
        raise Rejected(400, "expected_domain_server_ip_owner_email")
    if not all(isinstance(x, str) for x in data.values()):
        raise Rejected(400, "invalid_configuration")
    domain = data["domain"].strip().lower()
    if len(domain) > 253 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+", domain):
        raise Rejected(400, "invalid_domain")
    try:
        ip = ipaddress.ip_address(data["server_ip"].strip())
    except ValueError:
        raise Rejected(400, "invalid_server_ip")
    email = data["owner_email"].strip()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise Rejected(400, "invalid_owner_email")
    return {"domain": domain, "server_ip": str(ip), "owner_email": email}


class App:
    def __init__(self, setup, port=19200):
        self.setup, self.port = setup, port

    def __call__(self, env, start):
        code, content_type = 200, "application/json"
        try:
            hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
            if env.get("HTTP_HOST") not in hosts:
                raise Rejected(403, "local_host_required")
            origin = env.get("HTTP_ORIGIN")
            if origin and origin not in {"http://" + h for h in hosts}:
                raise Rejected(403, "same_origin_required")
            method, path = env["REQUEST_METHOD"], env.get("PATH_INFO", "/")
            assets = {"/": ("setup.html", "text/html; charset=utf-8"), "/setup.js": ("setup.js", "application/javascript"), "/setup.css": ("setup.css", "text/css")}
            if method == "GET" and path in assets:
                file, content_type = assets[path]
                body = (Path(__file__).parent / file).read_bytes()
            else:
                length = int(env.get("CONTENT_LENGTH") or 0)
                if not 0 <= length <= 16384:
                    raise Rejected(413, "request_too_large")
                data = json.loads(env["wsgi.input"].read(length)) if length else {}
                if not isinstance(data, dict):
                    raise Rejected(400, "invalid_json")
                auth = env.get("HTTP_AUTHORIZATION", "")
                token = auth[7:] if auth.startswith("Bearer ") else ""
                body = json.dumps(self.setup.call(method, path, token, data)).encode()
        except Rejected as error:
            code, body = error.status, json.dumps({"error": error.code}).encode()
        except (ValueError, TypeError):
            code, body = 400, b'{"error":"invalid_request"}'
        except Exception:
            code, body = 500, b'{"error":"setup_unavailable"}'
        labels = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found", 409: "Conflict", 413: "Content Too Large", 500: "Internal Server Error"}
        start(f"{code} {labels[code]}", [("Content-Type", content_type), ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"), ("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; form-action 'self'")])
        return [body]


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass  # Never log paths, queries or credentials from bootstrap requests.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default=".runtime/setup")
    parser.add_argument("--port", type=int, default=19200)
    args = parser.parse_args()
    setup = Setup(args.state)
    print(f"Setup: http://127.0.0.1:{args.port}", flush=True)
    print(f"Bootstrap credential file: {setup.directory.resolve() / 'bootstrap-token'} (removed after claim)", flush=True)
    with make_server("127.0.0.1", args.port, App(setup, args.port), handler_class=QuietHandler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
