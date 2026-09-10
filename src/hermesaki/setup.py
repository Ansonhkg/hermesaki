"""Private first-run control plane with explicitly authorized fresh mail deployment."""
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
from .setup_cloudflare import Cloudflare, CloudflareError, fingerprint, web_hosts
from .setup_preflight import host_checks
from .setup_services import Services, DeploymentError, dns_plan, private_write
from .setup_runtime import Runtime
from .setup_verify import verify as verify_services
from .setup_handover import handover
from .setup_agent import verify as verify_agent
from .setup_mail import validate_recipient, start as start_mail, verify as verify_mail
from .setup_network import issue as issue_network, accept as accept_network
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
            db.execute("CREATE TABLE IF NOT EXISTS mail_verification (id INTEGER PRIMARY KEY CHECK(id=1), attempt TEXT NOT NULL, session TEXT, result TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS agent_verification (id INTEGER PRIMARY KEY CHECK(id=1), result TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS network_probe (id INTEGER PRIMARY KEY CHECK(id=1), challenge TEXT, result TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS completion (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS verification (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS renewal (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS dkim (id INTEGER PRIMARY KEY CHECK(id=1), plan TEXT NOT NULL, progress TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS deployment (id INTEGER PRIMARY KEY CHECK(id=1), plan TEXT NOT NULL, progress TEXT)")
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
            completed = db.execute("SELECT value FROM completion WHERE id=1").fetchone()
            if completed:
                if method == "GET" and path == "/v1/setup":
                    return json.loads(completed["value"])
                raise Rejected(409, "setup_completed_use_operator")
            if method == "POST" and path in ("/v1/setup/network/challenge", "/v1/setup/network/result"):
                saved = db.execute("SELECT * FROM deployment WHERE id=1").fetchone()
                if not saved or not saved["progress"] or json.loads(saved["progress"]).get("state") != "services_running":
                    raise Rejected(409,"deploy_services_first")
                plan_id = json.loads(saved["plan"])["id"]
                if path.endswith("/challenge"):
                    challenge = issue_network(json.loads(row["settings"]),plan_id)
                    db.execute("INSERT OR REPLACE INTO network_probe VALUES(1,?,NULL)",(json.dumps(challenge),))
                    db.execute("DELETE FROM verification")
                    return challenge
                current = db.execute("SELECT challenge FROM network_probe WHERE id=1").fetchone()
                if not current or not current["challenge"]:raise Rejected(409,"new_network_challenge_required")
                try:result = accept_network(json.loads(current["challenge"]),data,plan_id)
                except (ValueError,TypeError,KeyError) as error:raise Rejected(409,"network_probe_invalid_or_expired")
                db.execute("UPDATE network_probe SET challenge=NULL,result=? WHERE id=1",(json.dumps(result),))
                db.execute("DELETE FROM verification")
                return result
            if method == "POST" and path in ("/v1/setup/mail/start", "/v1/setup/mail/verify", "/v1/setup/mail/reset"):
                saved = db.execute("SELECT * FROM deployment WHERE id=1").fetchone()
                if not saved or not saved["progress"] or json.loads(saved["progress"]).get("state") != "services_running":
                    raise Rejected(409,"deploy_services_first")
                plan=json.loads(saved["plan"])
                current=db.execute("SELECT * FROM mail_verification WHERE id=1").fetchone()
                runtime=Runtime(Services(self.directory))
                try:
                    if path.endswith("/reset"):
                        if data != {"confirm_new_test": True}:raise ValueError("confirm_new_test_required")
                        db.execute("DELETE FROM mail_verification")
                        db.execute("DELETE FROM verification")
                        return {"state":"ready"}
                    if path.endswith("/start"):
                        if set(data)!={"confirm_recipient"}:raise ValueError("confirm_external_recipient")
                        validate_recipient(plan,data["confirm_recipient"])
                        if current:
                            attempt=json.loads(current["attempt"])
                            if attempt["recipient"]!=data["confirm_recipient"]:raise ValueError("test_already_started_for_another_recipient")
                            if current["session"]:return json.loads(current["session"])
                        else:
                            attempt={"key":secrets.token_hex(12),"recipient":data["confirm_recipient"]}
                            db.execute("INSERT INTO mail_verification VALUES(1,?,NULL,NULL)",(json.dumps(attempt),))
                            db.commit()
                        session=start_mail(runtime,plan,attempt["recipient"],attempt["key"])
                        db.execute("UPDATE mail_verification SET session=? WHERE id=1",(json.dumps(session),))
                        return session
                    if not current or not current["session"]:raise ValueError("send_external_test_first")
                    if set(data)!={"original"}:raise ValueError("external_original_required")
                    result=verify_mail(runtime,json.loads(current["session"]),data["original"])
                    db.execute("UPDATE mail_verification SET result=? WHERE id=1",(json.dumps(result),))
                    db.execute("DELETE FROM verification")
                    return result
                except ValueError as error:raise Rejected(400,str(error))
                except DeploymentError:raise Rejected(409,"external_mail_check_unavailable_retry")
            if method == "POST" and path == "/v1/setup/agent/verify":
                saved = db.execute("SELECT * FROM deployment WHERE id=1").fetchone()
                if not saved or not saved["progress"] or json.loads(saved["progress"]).get("state") != "services_running":
                    raise Rejected(409,"deploy_services_first")
                try:
                    result = verify_agent(Runtime(Services(self.directory)),json.loads(row["settings"]),json.loads(saved["plan"]),data)
                except ValueError as error:
                    raise Rejected(400,str(error))
                db.execute("INSERT OR REPLACE INTO agent_verification VALUES(1,?)",(json.dumps(result),))
                db.execute("DELETE FROM verification")
                return result
            if method == "POST" and path == "/v1/setup/complete":
                saved = db.execute("SELECT * FROM deployment WHERE id=1").fetchone()
                if not saved or not saved["progress"] or json.loads(saved["progress"]).get("state") != "services_running":
                    raise Rejected(409, "deploy_services_first")
                plan = json.loads(saved["plan"])
                if data != {"confirm_plan_id":plan["id"]}:
                    raise Rejected(409, "exact_plan_confirmation_required")
                dkim = db.execute("SELECT progress FROM dkim WHERE id=1").fetchone()
                renewal = db.execute("SELECT value FROM renewal WHERE id=1").fetchone()
                # Re-run actual checks; saved JSON or caller-supplied booleans cannot complete setup.
                result = verify_services(Runtime(Services(self.directory)), json.loads(row["settings"]), plan,
                    bool(dkim and dkim["progress"] and json.loads(dkim["progress"]).get("state")=="dkim_published"), bool(renewal), self.network_result(db), self.agent_result(db), self.mail_result(db))
                db.execute("INSERT OR REPLACE INTO verification VALUES(1,?)", (json.dumps(result),))
                db.commit()
                try:
                    complete = handover(result, json.loads(row["settings"]), plan["id"])
                except ValueError as error:
                    raise Rejected(409, str(error))
                db.execute("INSERT INTO completion VALUES(1,?)", (json.dumps(complete),))
                (self.directory / "bootstrap-token").unlink(missing_ok=True)
                return complete
            if method == "POST" and path in ("/v1/setup/services/verify", "/v1/setup/services/renewal-check"):
                saved = db.execute("SELECT * FROM deployment WHERE id=1").fetchone()
                if not saved or not saved["progress"] or json.loads(saved["progress"]).get("state") != "services_running":
                    raise Rejected(409, "deploy_services_first")
                runtime = Runtime(Services(self.directory))
                if path.endswith("/renewal-check"):
                    try:
                        runtime.run(["docker","run","--rm","-v",str(runtime.root/"acme")+":/etc/letsencrypt","-v",str(runtime.root/"certbot-secret")+":/run/hermesaki-certbot:ro",
                            runtime.lock["certbot"]["image"],"renew","--dry-run","--non-interactive","--no-random-sleep-on-renew"])
                    except DeploymentError as error:
                        raise Rejected(409,str(error))
                    db.execute("INSERT OR REPLACE INTO renewal VALUES(1,?)",(json.dumps({"passed":True}),))
                    return {"renewal_verified":True,"complete":False}
                dkim = db.execute("SELECT progress FROM dkim WHERE id=1").fetchone()
                renewal = db.execute("SELECT value FROM renewal WHERE id=1").fetchone()
                result = verify_services(runtime,json.loads(row["settings"]),json.loads(saved["plan"]),
                    bool(dkim and dkim["progress"] and json.loads(dkim["progress"]).get("state")=="dkim_published"),bool(renewal), self.network_result(db), self.agent_result(db), self.mail_result(db))
                db.execute("INSERT OR REPLACE INTO verification VALUES(1,?)",(json.dumps(result),))
                return result
            if method == "POST" and path == "/v1/setup/services/credentials":
                saved = db.execute("SELECT progress FROM deployment WHERE id=1").fetchone()
                if not saved or not saved["progress"] or json.loads(saved["progress"]).get("state") != "services_running":
                    raise Rejected(409, "deploy_services_first")
                script = """from hermesaki.http import create_app
from pathlib import Path
import json
app=create_app();s=app.s.store
account=json.loads(Path('/state/first-mailbox.json').read_text())
print(json.dumps({'email':account['email'],'password':s.open(s.inbox(account['id'])['secret'],account['id']),'operator_token':Path('/state/operator-token').read_text()}))
"""
                try:
                    return json.loads(Runtime(Services(self.directory)).dc("run","--rm","-T","api","python","-",stdin=script))
                except DeploymentError as error:
                    raise Rejected(409,str(error))
            if method == "POST" and path in ("/v1/setup/dkim/plan", "/v1/setup/dkim/apply"):
                deployment = db.execute("SELECT * FROM deployment WHERE id=1").fetchone()
                if not deployment or not deployment["progress"] or json.loads(deployment["progress"]).get("state") != "services_running":
                    raise Rejected(409, "deploy_services_first")
                service_plan = json.loads(deployment["plan"])
                services = Services(self.directory)
                provider = self.cloudflare((self.directory / "cloudflare-token").read_text())
                try:
                    records = json.loads(Runtime(services).dc("run","--rm","-T","api","python","-m","hermesaki.setup_dkim"))
                    actions, conflicts, observed = dns_plan(provider,service_plan["zone_id"],records)
                    if path.endswith("/plan"):
                        plan = {"zone_id":service_plan["zone_id"],"actions":actions,"conflicts":conflicts,"apply_available":not conflicts}
                        plan["id"] = fingerprint({"records":records,"observed":observed})
                        db.execute("INSERT OR REPLACE INTO dkim VALUES(1,?,NULL)",(json.dumps(plan),))
                        return plan
                    saved = db.execute("SELECT * FROM dkim WHERE id=1").fetchone()
                    if not saved:raise DeploymentError("dkim_plan_required")
                    plan = json.loads(saved["plan"])
                    if data != {"confirm_plan_id":plan["id"]}:raise DeploymentError("exact_plan_confirmation_required")
                    if conflicts or records != [a["record"] for a in plan["actions"]]:raise DeploymentError("dkim_changed_review_again")
                    progress = json.loads(saved["progress"]) if saved["progress"] else {}
                    def checkpoint_dkim(value):
                        db.execute("UPDATE dkim SET progress=? WHERE id=1",(json.dumps(value),));db.commit()
                    services.apply_dns(provider,plan,progress,checkpoint_dkim)
                    progress["state"]="dkim_published";checkpoint_dkim(progress)
                    return {"state":"dkim_published","complete":False,"next_action":"verify_mail_and_access"}
                except (DeploymentError, CloudflareError) as error:
                    raise Rejected(409,str(error))
            if method == "POST" and path == "/v1/setup/services/apply":
                saved = db.execute("SELECT * FROM deployment WHERE id=1").fetchone()
                if not saved:
                    raise Rejected(409, "service_plan_required")
                plan = json.loads(saved["plan"])
                if data != {"confirm_plan_id": plan["id"]}:
                    raise Rejected(400, "exact_plan_confirmation_required")
                if not plan["apply_available"]:
                    raise Rejected(409, "service_plan_has_conflicts")
                settings = json.loads(row["settings"])
                provider = self.cloudflare((self.directory / "cloudflare-token").read_text())
                services = Services(self.directory)
                progress = json.loads(saved["progress"]) if saved["progress"] else {}
                def checkpoint_service(value):
                    db.execute("UPDATE deployment SET progress=? WHERE id=1", (json.dumps(value),))
                    db.commit()
                try:
                    if not progress:
                        web_plan = json.loads(db.execute("SELECT value FROM plans WHERE id=1").fetchone()[0])
                        web_progress = json.loads(db.execute("SELECT value FROM progress WHERE id=1").fetchone()[0])
                        fresh = services.plan(provider, settings, web_plan, web_progress, plan["options"])
                        if fresh["id"] != plan["id"]:
                            raise DeploymentError("service_plan_changed_review_again")
                        checks = host_checks(settings)
                        required = {"supported_host", "docker", "compose", "public_ip", "smtp_bind"}
                        passed = {c["id"] for c in checks["checks"] if c["state"] == "passed"}
                        if not required <= passed:
                            raise DeploymentError("host_prerequisites_not_met")
                        progress = {"plan_id":plan["id"], "state":"deploying", "steps":[]}
                        checkpoint_service(progress)
                    services.apply_dns(provider, plan, progress, checkpoint_service)
                    return Runtime(services).apply(settings, plan, progress, checkpoint_service, provider)
                except (DeploymentError, CloudflareError) as error:
                    if progress:
                        progress["error"] = str(error)
                        checkpoint_service(progress)
                    raise Rejected(409, str(error))
            if method == "POST" and path == "/v1/setup/services/plan":
                saved = db.execute("SELECT value FROM plans WHERE id=1").fetchone()
                progress = db.execute("SELECT value FROM progress WHERE id=1").fetchone()
                deployment = db.execute("SELECT progress FROM deployment WHERE id=1").fetchone()
                if deployment and deployment["progress"]:
                    raise Rejected(409, "service_deployment_started_cannot_replace_plan")
                if not saved or not progress:
                    raise Rejected(409, "apply_web_protection_first")
                try:
                    plan = Services(self.directory).plan(self.cloudflare((self.directory / "cloudflare-token").read_text()),
                        json.loads(row["settings"]), json.loads(saved["value"]), json.loads(progress["value"]), data)
                except (DeploymentError, CloudflareError) as error:
                    raise Rejected(409, str(error))
                db.execute("INSERT OR REPLACE INTO deployment VALUES(1,?,NULL)", (json.dumps(plan),))
                return plan
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
                    settings = json.loads(row["settings"])
                    plan = self.cloudflare(raw).plan(settings)
                    if not db.execute("SELECT 1 FROM progress").fetchone() and settings["domain"] != plan.get("zone_name",settings["domain"]) and not settings.get("operator_hostname"):
                        zone = plan["zone_name"]
                        prefix = settings["domain"][:-(len(zone)+1)].replace(".","-")
                        if len(prefix)>48:
                            prefix = digest(prefix)[:24]
                        settings.update(operator_hostname="hermesaki-"+prefix+"."+zone,webmail_hostname="inbox-"+prefix+"."+zone)
                        plan = self.cloudflare(raw).plan(settings)
                        db.execute("UPDATE state SET settings=? WHERE id=1",(json.dumps(settings),))
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
                db.execute("DELETE FROM verification")
                db.execute("DELETE FROM renewal")
                db.execute("DELETE FROM network_probe")
                db.execute("DELETE FROM agent_verification")
                db.execute("UPDATE mail_verification SET result=NULL")
                acme_credential = self.directory / "installation/certbot-secret/cloudflare.ini"
                if acme_credential.exists():
                    private_write(acme_credential, "dns_cloudflare_api_token = " + raw + "\n")
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
                deployment = db.execute("SELECT * FROM deployment WHERE id=1").fetchone()
                dkim = db.execute("SELECT * FROM dkim WHERE id=1").fetchone()
                result["dkim_plan"] = json.loads(dkim["plan"]) if dkim else None
                result["dkim_progress"] = json.loads(dkim["progress"]) if dkim and dkim["progress"] else None
                verification = db.execute("SELECT value FROM verification WHERE id=1").fetchone()
                result["service_verification"] = json.loads(verification["value"]) if verification else None
                result["service_plan"] = json.loads(deployment["plan"]) if deployment else None
                result["service_progress"] = json.loads(deployment["progress"]) if deployment and deployment["progress"] else None
                return self.next_actions(result)
            raise Rejected(404, "not_found")

    def mail_result(self, db):
        row = db.execute("SELECT result FROM mail_verification WHERE id=1").fetchone()
        return json.loads(row["result"]) if row and row["result"] else None

    def agent_result(self, db):
        row = db.execute("SELECT result FROM agent_verification WHERE id=1").fetchone()
        return json.loads(row["result"]) if row else None

    def network_result(self, db):
        row = db.execute("SELECT result FROM network_probe WHERE id=1").fetchone()
        return json.loads(row["result"]) if row and row["result"] else None

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
                action, method, path = "plan_private_services", "POST", "/v1/setup/services/plan"
                if result.get("service_plan"):
                    action, method, path = "review_and_deploy_services", "POST", "/v1/setup/services/apply"
                if (result.get("service_progress") or {}).get("state") == "services_running":
                    action, method, path = "verify_mail_and_access", "POST", "/v1/setup/services/verify"
                    result["operations"].extend({"method":"POST", "path":p} for p in ("/v1/setup/agent/verify","/v1/setup/mail/start","/v1/setup/mail/verify"))
                    if (result.get("service_verification") or {}).get("ready"):
                        action, method, path = "complete_setup", "POST", "/v1/setup/complete"
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
                  "limitations": ["Fresh mail deployment is available after a separate exact plan approval. Public verification and completion handover remain incomplete."]}
        if settings:
            result["plan"] = {"state": "draft", "changes_applied": False, "domain": settings["domain"],
                "mail_hostname": "mail." + settings["domain"],
                "webmail_hostname": web_hosts(settings)[1],
                "operator_hostname": web_hosts(settings)[0],
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
