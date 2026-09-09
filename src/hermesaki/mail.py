import base64
import email
import email.policy
import email.utils
import imaplib
import json
import re
import smtplib
import ssl
import urllib.request
from contextlib import contextmanager
from email.message import EmailMessage
from .store import Problem


class Mail:
    def __init__(self, config, store):
        self.config, self.store = config, store

    def verify_credentials(self, address, password):
        try:
            with imaplib.IMAP4_SSL(self.config.mail_host, self.config.mail_port,
                                  ssl_context=self.tls(), timeout=15) as mailbox:
                mailbox.login(address, password)
        except (imaplib.IMAP4.error, OSError):
            raise Problem(400, "mailbox_credentials_not_verified") from None

    def tls(self):
        return ssl.create_default_context(cafile=self.config.ca_file)

    @contextmanager
    def connect(self, inbox):
        m = imaplib.IMAP4_SSL(
            self.config.mail_host,
            self.config.mail_port,
            ssl_context=self.tls(),
            timeout=15,
        )
        try:
            m.login(inbox["email"], self.store.open(inbox["secret"], inbox["id"]))
            yield m
        finally:
            try:
                m.logout()
            except Exception:
                pass

    def select(self, m, folder):
        if (
            not isinstance(folder, str)
            or any(c in folder for c in "\r\n")
            or len(folder) > 200
        ):
            raise Problem(400, "invalid_folder")
        # Quote once; never allow IMAP syntax supplied by callers.
        name = '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'
        if m.select(name, readonly=True)[0] != "OK":
            raise Problem(404, "folder_not_found")
        return name

    def folders(self, inbox):
        with self.connect(inbox) as m:
            status, items = m.list()
            return [r.decode(errors="replace") for r in items or []]

    def messages(self, inbox, folder="INBOX", query="", limit=50):
        with self.connect(inbox) as m:
            self.select(m, folder)
            if query:
                if len(query) > 200 or any(c in query for c in "\r\n"):
                    raise Problem(400, "invalid_query")
                status, items = m.uid(
                    "search",
                    None,
                    "TEXT",
                    '"' + query.replace("\\", "\\\\").replace('"', '\\"') + '"',
                )
            else:
                status, items = m.uid("search", None, "ALL")
            ids = (items[0] or b"").split()[-min(max(int(limit), 1), 100) :][::-1]
            result = []
            for uid in ids:
                status, parts = m.uid(
                    "fetch",
                    uid,
                    "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO DATE MESSAGE-ID)] FLAGS)",
                )
                raw = next((r[1] for r in parts if isinstance(r, tuple)), None)
                if raw is None:
                    continue
                msg = email.message_from_bytes(raw, policy=email.policy.default)
                result.append(
                    {
                        "uid": uid.decode(),
                        "folder": folder,
                        "subject": str(msg.get("subject", "")),
                        "from": str(msg.get("from", "")),
                        "to": str(msg.get("to", "")),
                        "date": str(msg.get("date", "")),
                        "message_id": str(msg.get("message-id", "")),
                    }
                )
            return result

    def message(self, inbox, uid, folder="INBOX"):
        if not str(uid).isdigit():
            raise Problem(400, "invalid_uid")
        with self.connect(inbox) as m:
            self.select(m, folder)
            st, size = m.uid("fetch", str(uid), "(RFC822.SIZE)")
            values = b" ".join(r for r in size if isinstance(r, bytes))
            match = re.search(rb"RFC822.SIZE (\d+)", values)
            if not match:
                raise Problem(404, "message_not_found")
            if int(match[1]) > self.config.max_message_bytes:
                raise Problem(413, "message_too_large")
            st, parts = m.uid("fetch", str(uid), "(BODY.PEEK[])")
            raw = next((r[1] for r in parts if isinstance(r, tuple)), None)
            if raw is None:
                raise Problem(404, "message_not_found")
        msg = email.message_from_bytes(raw, policy=email.policy.default)
        body = msg.get_body(preferencelist=("plain",))
        attachments = []
        for i, part in enumerate(msg.iter_attachments()):
            data = part.get_payload(decode=True) or b""
            attachments.append(
                {
                    "id": str(i),
                    "filename": part.get_filename() or "attachment",
                    "content_type": part.get_content_type(),
                    "size": len(data),
                    "data": base64.b64encode(data).decode(),
                }
            )
        reports = []
        for part in msg.walk():
            if part.get_content_type() == "message/delivery-status":
                for report in part.get_payload():
                    action = report.get("Action")
                    if action in ("failed", "delayed", "delivered"):
                        reports.append(
                            {"action": action, "status": str(report.get("Status", ""))}
                        )
        return {
            "delivery_reports": reports,
            "uid": str(uid),
            "folder": folder,
            "from": str(msg.get("from", "")),
            "to": str(msg.get("to", "")),
            "subject": str(msg.get("subject", "")),
            "message_id": str(msg.get("message-id", "")),
            "references": str(msg.get("references", "")),
            "body_text": body.get_content() if body else "",
            "attachments": attachments,
        }

    def delete(self, inbox, uid, folder):
        if not str(uid).isdigit():
            raise Problem(400, "invalid_uid")
        with self.connect(inbox) as m:
            name = self.select(m, folder)
            m.select(name, readonly=False)
            if m.uid("store", str(uid), "+FLAGS.SILENT", r"(\Deleted)")[0] != "OK":
                raise Problem(502, "delete_failed")
            # UID EXPUNGE never removes another message already marked deleted.
            if m.uid("expunge", str(uid))[0] != "OK":
                raise Problem(502, "delete_failed")

    def send(self, inbox, content, message_id):
        msg = EmailMessage()
        msg["From"] = inbox["email"]
        msg["To"] = ", ".join(content["to"])
        msg["Subject"] = content["subject"]
        msg["Message-ID"] = message_id
        msg["Date"] = email.utils.formatdate(localtime=False)
        if content.get("in_reply_to"):
            msg["In-Reply-To"] = content["in_reply_to"]
            msg["References"] = content["references"]
        msg.set_content(content["body_text"])
        for attachment in content.get("attachments", []):
            msg.add_attachment(
                base64.b64decode(attachment["data"], validate=True),
                maintype="application",
                subtype="octet-stream",
                filename=attachment["filename"],
            )
        with smtplib.SMTP_SSL(
            self.config.mail_host, self.config.smtp_port, context=self.tls(), timeout=15
        ) as smtp:
            smtp.login(inbox["email"], self.store.open(inbox["secret"], inbox["id"]))
            # Partial acceptance is surfaced as uncertain, never retried blindly.
            refused = smtp.send_message(msg)
            if refused:
                raise RuntimeError("partial_delivery")


class Stalwart:
    def __init__(self, url, username, password, ca_file=None):
        self.url, self.username, self.password, self.ca_file = (
            url,
            username,
            password,
            ca_file,
        )

    def call(self, name, args):
        payload = {
            "using": ["urn:ietf:params:jmap:core"],
            "methodCalls": [[name, args, "0"]],
        }
        auth = base64.b64encode((self.username + ":" + self.password).encode()).decode()
        req = urllib.request.Request(
            self.url + "/jmap/",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": "Basic " + auth,
                "Content-Type": "application/json",
            },
        )
        ctx = (
            ssl.create_default_context(cafile=self.ca_file)
            if self.url.startswith("https")
            else None
        )
        with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
            x = json.load(r)
        method, body, _ = x["methodResponses"][0]
        if (
            method == "error"
            or body.get("notCreated")
            or body.get("notUpdated")
            or body.get("notDestroyed")
        ):
            raise Problem(502, "mail_provisioning_failed")
        return body

    def list(self, kind):
        return self.call("x:" + kind + "/get", {})["list"]

    def ensure(self, kind, key, value):
        existing = next((x for x in self.list(kind) if x.get(key) == value[key]), None)
        if existing:
            return existing["id"]
        return self.call(
            "x:" + kind + "/set",
            {
                "create": {
                    "new": {
                        k: v
                        for k, v in value.items()
                        if not (kind == "Account" and k == "emailAddress")
                    }
                }
            },
        )["created"]["new"]["id"]

    def account(self, address, password):
        local, domain = address.split("@")
        domain_id = self.ensure("Domain", "name", {"name": domain, "isEnabled": True})
        return self.ensure(
            "Account",
            "emailAddress",
            {
                "@type": "User",
                "name": local,
                "emailAddress": address,
                "domainId": domain_id,
                "roles": {"@type": "User"},
                "credentials": {"0": {"@type": "Password", "secret": password}},
            },
        )

    def delete_account(self, address):
        account = next(
            (x for x in self.list("Account") if x.get("emailAddress") == address), None
        )
        if account:
            self.call("x:Account/set", {"destroy": [account["id"]]})
