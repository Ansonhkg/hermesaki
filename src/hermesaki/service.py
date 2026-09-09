import base64
import email.utils
import hashlib
import json
import re
import secrets
from .store import Problem


class Service:
    def __init__(self, config, store, mail, provision=None):
        self.config, self.store, self.mail, self.provision = (
            config,
            store,
            mail,
            provision,
        )

    def permit(self, actor, scope, inbox=None):
        if scope not in actor["scopes"]:
            raise Problem(403, "scope_denied")
        if inbox is not None and actor.get("inbox") != inbox:
            raise Problem(403, "mailbox_denied")

    def create_inbox(self, actor, address):
        self.permit(actor, "admin")
        if not isinstance(address, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9._+-]{0,63}@" + re.escape(self.config.domain), address
        ):
            raise Problem(400, "invalid_address")
        # Record the credential before provisioning so retries use the same secret.
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM inboxes WHERE email=?", (address,)
            ).fetchone()
            if not row:
                ident = secrets.token_hex(12)
                password = secrets.token_urlsafe(32)
                db.execute(
                    "INSERT INTO inboxes VALUES(?,?,?,0)",
                    (ident, address, self.store.seal(password, ident)),
                )
            else:
                ident = row["id"]
                password = self.store.open(row["secret"], ident)
        if self.provision:
            self.provision.account(address, password)
        with self.store.db() as db:
            db.execute("UPDATE inboxes SET active=1 WHERE id=?", (ident,))
        self.store.audit(actor["id"], "inbox.create", ident)
        return {"id": ident, "email": address}

    def import_inbox(self, actor, address, password):
        """Adopt an existing mailbox without changing its password or mail data."""
        self.permit(actor, "admin")
        if not isinstance(address, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9._+-]{0,63}@" + re.escape(self.config.domain), address
        ):
            raise Problem(400, "invalid_address")
        if not isinstance(password, str) or not 1 <= len(password) <= 1024:
            raise Problem(400, "invalid_mailbox_credential")
        # Verify before persisting or replacing a working credential.
        self.mail.verify_credentials(address, password)
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT id FROM inboxes WHERE email=?", (address,)).fetchone()
            ident = existing["id"] if existing else secrets.token_hex(12)
            secret = self.store.seal(password, ident)
            if existing:
                db.execute("UPDATE inboxes SET secret=?,active=1 WHERE id=?", (secret, ident))
            else:
                db.execute("INSERT INTO inboxes VALUES(?,?,?,1)", (ident, address, secret))
        self.store.audit(actor["id"], "inbox.import", ident)
        return {"id": ident, "email": address, "imported": True}

    def revoke(self, actor, ident):
        self.permit(actor, "admin")
        with self.store.db() as db:
            db.execute("UPDATE tokens SET revoked=1 WHERE id=?", (ident,))
        self.store.audit(actor["id"], "token.revoke", ident)
        return {"revoked": True}

    def read(self, actor, inbox, action, **args):
        self.permit(actor, "mail.read", inbox)
        account = self.store.inbox(inbox)
        if action == "folders":
            result = self.mail.folders(account)
        elif action == "messages":
            result = self.mail.messages(account, **args)
        else:
            result = self.mail.message(account, **args)
        self.store.audit(actor["id"], "mail." + action, inbox)
        return result

    def send(self, actor, inbox, content, idem, reply_uid=None, folder="INBOX"):
        self.permit(actor, "mail.write", inbox)
        self.store.inbox(inbox)
        if not isinstance(idem, str) or not 1 <= len(idem) <= 128:
            raise Problem(400, "idempotency_key_required")
        content = dict(content)
        if reply_uid:
            self.permit(actor, "mail.read", inbox)
            original = self.mail.message(self.store.inbox(inbox), reply_uid, folder)
            content.update(
                to=[email.utils.parseaddr(original["from"])[1]],
                subject=original["subject"]
                if original["subject"].lower().startswith("re:")
                else "Re: " + original["subject"],
                in_reply_to=original["message_id"],
                references=(
                    original["references"] + " " + original["message_id"]
                ).strip(),
            )
        recipients = content.get("to")
        if (
            not isinstance(recipients, list)
            or not 1 <= len(recipients) <= 20
            or any(
                not isinstance(x, str)
                or not re.fullmatch(r"[^\s<>@,;]+@[^\s<>@,;]+", x)
                for x in recipients
            )
        ):
            raise Problem(400, "invalid_recipients")
        for field in ("subject", "body_text"):
            if not isinstance(content.get(field), str):
                raise Problem(400, "invalid_message")
        for field in ("subject", "in_reply_to", "references"):
            if any(x in content.get(field, "") for x in ("\r", "\n")):
                raise Problem(400, "invalid_header")
        if len(json.dumps(content).encode()) > self.config.max_message_bytes:
            raise Problem(413, "message_too_large")
        for a in content.get("attachments", []):
            if not isinstance(a.get("filename"), str) or any(
                c in a["filename"] for c in "\r\n"
            ):
                raise Problem(400, "invalid_attachment")
            try:
                base64.b64decode(a["data"], validate=True)
            except Exception:
                raise Problem(400, "invalid_attachment")
        fingerprint = hashlib.sha256(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id,fingerprint,state,message_id FROM jobs WHERE inbox=? AND idem=?",
                (inbox, idem),
            ).fetchone()
            if row:
                if row["fingerprint"] != fingerprint:
                    raise Problem(409, "idempotency_conflict")
                return {k: row[k] for k in ("id", "state", "message_id")}
            ident = secrets.token_hex(16)
            mid = "<" + ident + "@" + self.config.domain + ">"
            db.execute(
                "INSERT INTO jobs(id,inbox,idem,fingerprint,message,state,due,message_id) VALUES(?,?,?,?,?,?,?,?)",
                (
                    ident,
                    inbox,
                    idem,
                    fingerprint,
                    self.store.seal(content, ident),
                    "queued",
                    self.store.clock(),
                    mid,
                ),
            )
        self.store.audit(actor["id"], "mail.queue", ident)
        return {"id": ident, "state": "queued", "message_id": mid}

    def confirmation(self, actor, inbox, uid, folder):
        self.permit(actor, "mail.delete", inbox)
        self.store.inbox(inbox)
        raw = secrets.token_urlsafe(32)
        action = json.dumps([str(uid), folder])
        with self.store.db() as db:
            db.execute(
                "INSERT INTO confirmations VALUES(?,?,?,?,0)",
                (
                    hashlib.sha256(raw.encode()).hexdigest(),
                    inbox,
                    action,
                    self.store.clock() + 60,
                ),
            )
        return {
            "confirmation": raw,
            "expires_in": 60,
            "action": "delete",
            "uid": uid,
            "folder": folder,
        }

    def delete(self, actor, inbox, uid, folder, confirmation):
        self.permit(actor, "mail.delete", inbox)
        with self.store.db() as db:
            cur = db.execute(
                "UPDATE confirmations SET used=1 WHERE hash=? AND inbox=? AND action=? AND expires>? AND used=0",
                (
                    hashlib.sha256(confirmation.encode()).hexdigest(),
                    inbox,
                    json.dumps([str(uid), folder]),
                    self.store.clock(),
                ),
            )
            if not cur.rowcount:
                raise Problem(403, "confirmation_required")
        self.mail.delete(self.store.inbox(inbox), uid, folder)
        self.store.audit(actor["id"], "mail.delete", inbox)
        return {"deleted": True}

    def overview(self, actor, table, offset=0):
        self.permit(actor, "admin")
        columns = {
            "inboxes": "id,email,active",
            "jobs": "id,inbox,state,attempts,due,message_id,error",
            "events": "id,inbox,kind,created",
            "deliveries": "id,hook,event,state,attempts,due,error",
            "audit": "id,actor,action,resource,result,created",
            "drafts": "id,inbox,event,created",
            "tokens": "id,inbox,scopes,expires,revoked",
        }
        if table not in columns:
            raise Problem(404, "not_found")
        with self.store.db() as db:
            rows = db.execute(
                "SELECT "
                + columns[table]
                + " FROM "
                + table
                + " ORDER BY rowid DESC LIMIT 51 OFFSET ?",
                (max(0, int(offset)),),
            ).fetchall()
        return {
            "items": [dict(x) for x in rows[:50]],
            "has_more": len(rows) > 50,
            "offset": offset,
        }
