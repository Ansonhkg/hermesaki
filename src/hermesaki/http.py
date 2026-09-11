import json
import secrets
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs
import jwt
from . import sessions
from .config import Config
from .store import Store, Problem
from .mail import Mail, Stalwart
from .service import Service
from .worker import target


class App:
    def __init__(self, service):
        self.s = service
        self.c = service.config
        self.jwks = (
            jwt.PyJWKClient(
                "https://"
                + self.c.access_team
                + ".cloudflareaccess.com/cdn-cgi/access/certs"
            )
            if self.c.mode == "production"
            else None
        )

    def __call__(self, environ, start):
        status = 200
        actor = None
        extra_headers = []
        try:
            path = environ.get("PATH_INFO", "/")
            method = environ["REQUEST_METHOD"]
            if path == "/healthz":
                result = {"status": "ok"}
            else:
                if self.jwks:
                    token = environ.get("HTTP_CF_ACCESS_JWT_ASSERTION", "")
                    try:
                        jwt.decode(
                            token,
                            self.jwks.get_signing_key_from_jwt(token).key,
                            algorithms=["RS256"],
                            audience=self.c.access_aud,
                            issuer="https://"
                            + self.c.access_team
                            + ".cloudflareaccess.com",
                        )
                    except Exception:
                        raise Problem(401, "access_required")
                if method == "GET" and path in ("/onboarding", "/onboarding/", "/ui/onboarding", "/ui/onboarding/", "/ui/onboarding/index.html", "/ui/", "/ui/index.html"):
                    start("303 See Other", [("Location", "/inboxes"), ("Cache-Control", "no-store")])
                    return [b""]
                if (path.startswith("/ui/") or path in ("/welcome", "/welcome/setup")) and method == "GET":
                    root = Path(__file__).resolve().parents[2] / "landing"
                    relative = {"/welcome": "index.html", "/welcome/setup": "get-started.html"}.get(path, path.removeprefix("/ui/") or "index.html")
                    file = (root / relative).resolve()
                    if not file.is_relative_to(root.resolve()):
                        raise Problem(404, "not_found")
                    if file.is_dir():
                        file = file / "index.html"
                    if not file.is_file():
                        raise Problem(404, "not_found")
                    start(
                        "200 OK",
                        [
                            (
                                "Content-Type",
                                mimetypes.guess_type(str(file))[0]
                                or "application/octet-stream",
                            ),
                            ("Cache-Control", "no-store"),
                            ("X-Content-Type-Options", "nosniff"),
                            (
                                "Content-Security-Policy",
                                "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self'; connect-src 'self'; frame-ancestors 'none'",
                            ),
                        ],
                    )
                    return [file.read_bytes()]
                if (path in ("/", "/login", "/inboxes", "/agents", "/activity", "/settings", "/docs") or path.startswith(("/docs/", "/settings/"))) and method == "GET":
                    body = Path(__file__).with_name("operator.html").read_bytes()
                    start(
                        "200 OK",
                        [
                            ("Content-Type", "text/html; charset=utf-8"),
                            (
                                "Content-Security-Policy",
                                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'",
                            ),
                            ("Cache-Control", "no-store"),
                        ],
                    )
                    return [body]
                header = environ.get("HTTP_AUTHORIZATION", "")
                if path == '/v1/session' and method == 'POST':
                    sessions.same_origin(self.c,environ)
                    if not header.startswith('Bearer '): raise Problem(401,'token_required')
                    raw,expires=sessions.issue(self.s.store,header[7:],sessions.cookie_id(environ))
                    start('200 OK',[('Content-Type','application/json'),('Cache-Control','no-store'),sessions.header(self.c,raw)])
                    return [json.dumps({'authenticated':True,'expires':expires}).encode()]
                if header.startswith('Bearer '):
                    actor = self.s.store.auth(header[7:])
                else:
                    if method not in ('GET','HEAD'): sessions.same_origin(self.c,environ)
                    actor = sessions.authenticate(self.s.store,sessions.cookie_id(environ))
                if path == '/v1/session':
                    self.s.permit(actor,'admin')
                    if method == 'DELETE':
                        sessions.revoke(self.s.store,sessions.cookie_id(environ))
                        extra_headers.append(sessions.header(self.c,age=0))
                    elif method != 'GET': raise Problem(405,'method_not_allowed')
                    start('200 OK',[('Content-Type','application/json'),('Cache-Control','no-store')]+extra_headers)
                    return [json.dumps({'authenticated':method=='GET'}).encode()]
                length = int(environ.get("CONTENT_LENGTH") or 0)
                if length > self.c.max_message_bytes or length < 0:
                    raise Problem(413, "request_too_large")
                data = json.loads(environ["wsgi.input"].read(length)) if length else {}
                if not isinstance(data, dict):
                    raise Problem(400, "invalid_json")
                query = {
                    k: v[0]
                    for k, v in parse_qs(environ.get("QUERY_STRING", "")).items()
                }
                if path == "/mcp":
                    if method != "POST":
                        raise Problem(405, "method_not_allowed")
                    if "id" not in data:
                        status = 202
                        result = {}
                    else:
                        try:
                            result = {
                                "jsonrpc": "2.0",
                                "id": data["id"],
                                "result": self.mcp(actor, data),
                            }
                        except Problem as e:
                            result = {
                                "jsonrpc": "2.0",
                                "id": data["id"],
                                "error": {"code": -32000, "message": e.code},
                            }
                else:
                    result = self.route(
                        actor, method, path.strip("/").split("/"), data, query, environ
                    )
        except Problem as e:
            status = e.status
            result = {"error": e.code}
        except (ValueError, TypeError, KeyError):
            status = 400
            result = {"error": "invalid_request"}
        except Exception:
            status = 502
            result = {"error": "service_unavailable"}
        if status >= 400:
            self.s.store.audit(
                actor["id"] if actor else "anonymous",
                "request.denied",
                None,
                result["error"],
            )
        start(
            str(status)
            + " "
            + {
                200: "OK",
                202: "Accepted",
                400: "Bad Request",
                401: "Unauthorized",
                403: "Forbidden",
                404: "Not Found",
                405: "Method Not Allowed",
                409: "Conflict",
                413: "Content Too Large",
                502: "Bad Gateway",
            }.get(status, "Error"),
            [
                ("Content-Type", "application/json"),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
            ],
        )
        return [json.dumps(result).encode()]

    def route(self, a, method, p, d, q, e):
        s = self.s
        if p[:3] == ["v1", "operator", "mcp-connection"]:
            from .mcp_connection import handle
            return handle(s.store, self.c, a, method, '/'.join(p[3:]), d)
        if p[:3] == ["v1", "operator", "infrastructure"]:
            s.permit(a, "admin")
            from . import infrastructure
            from .setup_cloudflare import CloudflareError
            try:
                if len(p) == 3 and method == "GET":
                    return {**infrastructure.inventory(s.store, self.c), "pending_plan": infrastructure.pending(s.store)}
                if p[3:] == ["connect"] and method == "POST":
                    return infrastructure.connect(s.store, self.c, d)
                if p[3:] == ["plan"] and method == "POST":
                    return infrastructure.plan(s.store, self.c, d)
                if p[3:] == ["apply"] and method == "POST":
                    return infrastructure.apply(s.store, self.c, d)
                raise Problem(404, "not_found")
            except CloudflareError as error:
                raise Problem(502, str(error)) from None
        if p[:3] == ["v1", "operator", "configuration"]:
            s.permit(a, "admin")
            from . import operator_configuration as configuration
            if len(p) == 3 and method == "GET":
                return configuration.read(self.c)
            if p[3:] == ["plan"] and method == "POST":
                return configuration.plan(s.store, self.c, d)
            if p[3:] == ["apply"] and method == "POST":
                return configuration.apply(s.store, self.c, d)
            raise Problem(404, "not_found")
        if p == ["v1", "settings"] and method == "GET":
            s.permit(a, "admin")
            from .operator_configuration import read
            return {
                "webmail_url": read(self.c)["webmail_url"],
                "domain": self.c.domain,
                "mode": self.c.mode,
                "public_url": self.c.public_url,
            }
        if (
            len(p) == 4
            and p[:2] == ["v1", "inboxes"]
            and p[3] == "test-message"
            and method == "POST"
        ):
            s.permit(a, "admin")
            if self.c.mode != "development":
                raise Problem(403, "local_test_only")
            dest = s.store.inbox(p[2])
            sender = s.create_inbox(a, "onboarding-test@" + self.c.domain)
            return s.send(
                {"id": a["id"], "inbox": sender["id"], "scopes": ["mail.write"]},
                sender["id"],
                {
                    "to": [dest["email"]],
                    "subject": "Hello from Hermesaki",
                    "body_text": "Your real local inbox is ready. Read this message through MCP, the SDK or CLI.",
                },
                e.get("HTTP_IDEMPOTENCY_KEY"),
            )
        if len(p) == 4 and p[:2] == ["v1", "inboxes"] and p[3] == "webmail-credentials" and method == "GET":
            s.permit(a, "admin")
            account = s.store.inbox(p[2])
            from .operator_configuration import read
            s.store.audit(a["id"], "webmail.credentials.read", p[2])
            return {"email": account["email"], "password": s.store.open(account["secret"], p[2]),
                    "webmail_url": read(self.c)["webmail_url"]}
        if p == ["v1", "inboxes", "import"] and method == "POST":
            return s.import_inbox(a, d.get("email"), d.get("password"))
        if p == ["v1", "inboxes"] and method == "POST":
            return s.create_inbox(a, d["email"])
        if p == ["v1", "inboxes"] and method == "GET":
            return s.overview(a, "inboxes", int(q.get("offset", 0)))
        if (
            len(p) == 4
            and p[:2] == ["v1", "jobs"]
            and p[3] == "resolve"
            and method == "POST"
        ):
            s.permit(a, "admin")
            if (
                d.get("state") not in ("submitted", "failed")
                or d.get("confirm") != p[2]
            ):
                raise Problem(400, "explicit_resolution_required")
            with s.store.db() as db:
                cur = db.execute(
                    "UPDATE jobs SET state=?,error='operator_resolved' WHERE id=? AND state='uncertain'",
                    (d["state"], p[2]),
                )
                if not cur.rowcount:
                    raise Problem(409, "job_not_uncertain")
            s.store.audit(a["id"], "job.resolve." + d["state"], p[2])
            return {"resolved": True}

        if p == ["v1", "tokens"] and method == "POST":
            s.permit(a, "admin")
            ttl = d.get("ttl", 2592000)
            if not isinstance(ttl, int) or not 1 <= ttl <= 31536000:
                raise Problem(400, "invalid_ttl")
            return s.store.token(d.get("inbox_id"), d["scopes"], ttl)
        if len(p) == 3 and p[:2] == ["v1", "tokens"] and method == "DELETE":
            return s.revoke(a, p[2])
        if len(p) == 3 and p[:2] == ["v1", "inboxes"] and method == "DELETE":
            s.permit(a, "admin")
            with s.store.db() as db:
                row = db.execute("SELECT * FROM inboxes WHERE id=?", (p[2],)).fetchone()
            if not row:
                raise Problem(404, "inbox_not_found")
            if d.get("confirm_email") != row["email"]:
                raise Problem(400, "confirm_email_required")
            with s.store.db() as db:
                db.execute("UPDATE inboxes SET active=0 WHERE id=?", (p[2],))
                db.execute("UPDATE tokens SET revoked=1 WHERE inbox=?", (p[2],))
                db.execute(
                    "UPDATE jobs SET state='failed',error='inbox_deleted' WHERE inbox=? AND state='queued'",
                    (p[2],),
                )
            if s.provision:
                s.provision.delete_account(row["email"])
            s.store.audit(a["id"], "inbox.delete", p[2])
            return {"deleted": True}

        if len(p) == 3 and p[:2] == ["v1", "operator"] and method == "GET":
            return s.overview(a, p[2], int(q.get("offset", 0)))
        if (
            len(p) == 4
            and p[:2] == ["v1", "deliveries"]
            and p[3] == "replay"
            and method == "POST"
        ):
            s.permit(a, "admin")
            with s.store.db() as db:
                cur = db.execute(
                    "UPDATE deliveries SET state='pending',attempts=0,due=? WHERE id=? AND state='dead'",
                    (s.store.clock(), p[2]),
                )
                if not cur.rowcount:
                    raise Problem(409, "not_dead_letter")
            s.store.audit(a["id"], "webhook.replay", p[2])
            return {"replayed": True}
        if len(p) >= 4 and p[:2] == ["v1", "inboxes"]:
            inbox, resource = p[2:4]
            folder = q.get("folder", d.get("folder", "INBOX"))
            if resource == "folders" and method == "GET":
                return s.read(a, inbox, "folders")
            if resource == "messages":
                if len(p) == 4 and method == "GET":
                    return s.read(
                        a,
                        inbox,
                        "messages",
                        folder=folder,
                        query=q.get("query", ""),
                        limit=int(q.get("limit", 50)),
                    )
                if len(p) == 4 and method == "POST":
                    return s.send(a, inbox, d, e.get("HTTP_IDEMPOTENCY_KEY"))
                if len(p) == 5 and method == "GET":
                    return s.read(a, inbox, "message", uid=p[4], folder=folder)
                if len(p) == 5 and method == "DELETE":
                    return s.delete(a, inbox, p[4], folder, d.get("confirmation", ""))
                if len(p) == 6 and p[5] == "confirmation" and method == "POST":
                    return s.confirmation(a, inbox, p[4], folder)
                if len(p) == 6 and p[5] == "reply" and method == "POST":
                    return s.send(
                        a, inbox, d, e.get("HTTP_IDEMPOTENCY_KEY"), p[4], folder
                    )
            if resource == "webhooks" and method == "POST":
                s.permit(a, "mail.write", inbox)
                s.store.inbox(inbox)
                target(d["url"], self.c)
                ident = secrets.token_hex(12)
                secret = secrets.token_urlsafe(32)
                with s.store.db() as db:
                    db.execute(
                        "INSERT INTO hooks VALUES(?,?,?,?,1)",
                        (ident, inbox, d["url"], s.store.seal(secret, ident)),
                    )
                return {"id": ident, "secret": secret}
            if (
                resource == "drafts"
                and len(p) == 6
                and p[5] == "send"
                and method == "POST"
            ):
                s.permit(a, "mail.read", inbox)
                s.permit(a, "mail.write", inbox)
                if d.get("confirm") != p[4]:
                    raise Problem(400, "draft_approval_required")
                with s.store.db() as db:
                    row = db.execute(
                        "SELECT * FROM drafts WHERE id=? AND inbox=?", (p[4], inbox)
                    ).fetchone()
                if not row:
                    raise Problem(404, "draft_not_found")
                draft = s.store.open(row["content"], row["id"])
                return s.send(
                    a,
                    inbox,
                    {"body_text": d.get("body_text", draft["body_text"])},
                    "draft:" + row["id"],
                    draft["reply_uid"],
                    draft["folder"],
                )
            if resource == "drafts" and method == "GET":
                s.permit(a, "mail.read", inbox)
                s.store.inbox(inbox)
                with s.store.db() as db:
                    rows = db.execute(
                        "SELECT * FROM drafts WHERE inbox=? ORDER BY created DESC LIMIT 50",
                        (inbox,),
                    ).fetchall()
                return [
                    {"id": r["id"], **s.store.open(r["content"], r["id"])} for r in rows
                ]
        raise Problem(404, "not_found")

    def mcp(self, a, d):
        method = d.get("method")
        params = d.get("params", {})
        if method == "initialize":
            return {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "hermesaki", "version": "0.1.0"},
            }
        if method == "ping":
            return {}
        definitions = {
            "list_folders": {},
            "search_messages": {"query": {"type": "string"}},
            "read_message": {"uid": {"type": "string"}},
            "get_attachment": {
                "uid": {"type": "string"},
                "attachment_id": {"type": "string"},
            },
            "send_message": {
                "to": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "body_text": {"type": "string"},
                "idempotency_key": {"type": "string"},
            },
            "reply_message": {
                "uid": {"type": "string"},
                "body_text": {"type": "string"},
                "idempotency_key": {"type": "string"},
            },
            "confirm_delete": {"uid": {"type": "string"}},
            "delete_message": {
                "uid": {"type": "string"},
                "confirmation": {"type": "string"},
            },
        }
        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": name,
                        "description": name.replace("_", " "),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "inbox_id": {"type": "string"},
                                "folder": {"type": "string"},
                                **props,
                            },
                            "required": ["inbox_id"]
                            + ([k for k in props] if name != "search_messages" else []),
                            "additionalProperties": False,
                        },
                        "annotations": {
                            "readOnlyHint": name
                            in (
                                "list_folders",
                                "search_messages",
                                "read_message",
                                "get_attachment",
                            ),
                            "destructiveHint": name == "delete_message",
                        },
                    }
                    for name, props in definitions.items()
                ]
            }
        if method != "tools/call":
            raise Problem(400, "unknown_method")
        name = params["name"]
        args = dict(params.get("arguments", {}))
        inbox = args.pop("inbox_id")
        folder = args.pop("folder", "INBOX")
        s = self.s
        if name == "list_folders":
            r = s.read(a, inbox, "folders")
        elif name == "search_messages":
            r = s.read(a, inbox, "messages", folder=folder, query=args.get("query", ""))
        elif name in ("read_message", "get_attachment"):
            r = s.read(a, inbox, "message", uid=args["uid"], folder=folder)
            if name == "get_attachment":
                r = next(
                    (x for x in r["attachments"] if x["id"] == args["attachment_id"]),
                    None,
                )
                if r is None:
                    raise Problem(404, "attachment_not_found")
        elif name in ("send_message", "reply_message"):
            idem = args.pop("idempotency_key")
            uid = args.pop("uid", None)
            r = s.send(
                a, inbox, args, idem, uid if name == "reply_message" else None, folder
            )
        elif name == "confirm_delete":
            r = s.confirmation(a, inbox, args["uid"], folder)
        elif name == "delete_message":
            r = s.delete(a, inbox, args["uid"], folder, args["confirmation"])
        else:
            raise Problem(400, "unknown_tool")
        return {"content": [{"type": "text", "text": json.dumps(r)}], "isError": False}


def create_app():
    c = Config.load()
    s = Store(c.state)
    credentials = json.loads((Path(c.state) / "management.json").read_text())
    mail = Mail(c, s)
    return App(
        Service(
            c,
            s,
            mail,
            Stalwart(
                c.management_url,
                credentials["username"],
                credentials["password"],
                c.ca_file,
            ),
        )
    )
