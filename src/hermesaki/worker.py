import fcntl
from pathlib import Path
import hashlib
import hmac
import http.client
import ipaddress
import smtplib
import socket
import ssl
import time
from urllib.parse import urlsplit
from .store import Problem


def target(url, config):
    p = urlsplit(url)
    if (
        p.username
        or p.password
        or p.fragment
        or p.scheme not in ("https", "http")
        or not p.hostname
    ):
        raise Problem(400, "invalid_webhook_url")
    if p.hostname not in config.webhook_hosts:
        raise Problem(400, "webhook_host_not_allowed")
    if config.mode == "production" and p.scheme != "https":
        raise Problem(400, "https_required")
    return p


def deliver(url, body, secret, config, now):
    p = target(url, config)
    port = p.port or (443 if p.scheme == "https" else 80)
    addresses = socket.getaddrinfo(p.hostname, port, type=socket.SOCK_STREAM)
    ips = [a[4][0] for a in addresses]
    if config.mode == "production" and any(
        not ipaddress.ip_address(ip).is_global for ip in ips
    ):
        raise Problem(400, "private_webhook_address")
    # Resolve once and connect to the validated IP. TLS still authenticates the hostname.
    c = http.client.HTTPConnection(p.hostname, port, timeout=10)
    sock = socket.create_connection((ips[0], port), timeout=10)
    if p.scheme == "https":
        sock = ssl.create_default_context().wrap_socket(
            sock, server_hostname=p.hostname
        )
    c.sock = sock
    stamp = str(int(now))
    signature = hmac.new(
        secret.encode(), stamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    try:
        c.request(
            "POST",
            (p.path or "/") + ("?" + p.query if p.query else ""),
            body,
            {
                "Content-Type": "application/json",
                "X-Hermesaki-Timestamp": stamp,
                "X-Hermesaki-Signature": "v1=" + signature,
            },
        )
        r = c.getresponse()
        r.read(1024)
        if not 200 <= r.status < 300:
            raise Problem(502, "webhook_http_" + str(r.status))
    finally:
        c.close()


def verify_signature(body, timestamp, signature, secret, now, tolerance=300):
    try:
        if abs(now - int(timestamp)) > tolerance:
            return False
        wanted = (
            "v1="
            + hmac.new(
                secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256
            ).hexdigest()
        )
        return hmac.compare_digest(wanted, signature)
    except (ValueError, TypeError):
        return False


class Worker:
    def __init__(self, config, store, mail, sender=deliver):
        self.config, self.store, self.mail, self.sender = config, store, mail, sender

    def recover(self):
        # A process lost after SMTP acceptance cannot safely resend automatically.
        with self.store.db() as db:
            db.execute(
                "UPDATE jobs SET state='uncertain',error='worker_interrupted' WHERE state='sending'"
            )
            db.execute("UPDATE deliveries SET state='pending' WHERE state='sending'")

    def job(self):
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE state='queued' AND due<=? ORDER BY due LIMIT 1",
                (self.store.clock(),),
            ).fetchone()
            if not row:
                return False
            db.execute(
                "UPDATE jobs SET state='sending',attempts=attempts+1 WHERE id=?",
                (row["id"],),
            )
        state, error = "submitted", None
        try:
            self.mail.send(
                self.store.inbox(row["inbox"]),
                self.store.open(row["message"], row["id"]),
                row["message_id"],
            )
        except (
            smtplib.SMTPRecipientsRefused,
            smtplib.SMTPDataError,
            smtplib.SMTPSenderRefused,
        ) as e:
            code = getattr(e, "smtp_code", None)
            if isinstance(e, smtplib.SMTPRecipientsRefused):
                code = next(iter(e.recipients.values()))[0]
            state = (
                "queued"
                if code
                and 400 <= code < 500
                and row["attempts"] + 1 < self.config.max_attempts
                else "failed"
            )
            error = "smtp_rejected"
        except Exception:
            state, error = "uncertain", "delivery_unconfirmed"
        with self.store.db() as db:
            db.execute(
                "UPDATE jobs SET state=?,error=?,due=? WHERE id=?",
                (
                    state,
                    error,
                    self.store.clock() + min(3600, 2 ** (row["attempts"] + 1)),
                    row["id"],
                ),
            )
        self.store.event(
            row["inbox"],
            "message." + state,
            row["id"] + ":" + str(row["attempts"]),
            {"job_id": row["id"], "message_id": row["message_id"]},
        )
        return True

    def webhook(self):
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT d.*,h.url,h.secret,e.body FROM deliveries d JOIN hooks h ON h.id=d.hook JOIN events e ON e.id=d.event WHERE d.state='pending' AND d.due<=? AND h.active=1 ORDER BY d.due LIMIT 1",
                (self.store.clock(),),
            ).fetchone()
            if not row:
                return False
            db.execute(
                "UPDATE deliveries SET state='sending',attempts=attempts+1 WHERE id=?",
                (row["id"],),
            )
        state, error = "delivered", None
        try:
            self.sender(
                row["url"],
                row["body"].encode(),
                self.store.open(row["secret"], row["hook"]),
                self.config,
                self.store.clock(),
            )
        except Exception:
            state = (
                "dead" if row["attempts"] + 1 >= self.config.max_attempts else "pending"
            )
            error = "webhook_delivery_failed"
        with self.store.db() as db:
            db.execute(
                "UPDATE deliveries SET state=?,error=?,due=? WHERE id=?",
                (
                    state,
                    error,
                    self.store.clock() + min(3600, 2 ** (row["attempts"] + 1)),
                    row["id"],
                ),
            )
        return True

    def poll(self):
        with self.store.db() as db:
            accounts = [
                dict(x) for x in db.execute("SELECT * FROM inboxes WHERE active=1")
            ]
        for inbox in accounts:
            try:
                with self.mail.connect(inbox) as m:
                    self.mail.select(m, "INBOX")
                    validity = (m.response("UIDVALIDITY")[1] or [b"0"])[0].decode()
                    status, items = m.uid("search", None, "ALL")
                    uids = (items[0] or b"").split()
                for uid in uids:
                    ident = self.store.event(
                        inbox["id"],
                        "message.received",
                        validity + ":" + uid.decode(),
                        {
                            "uid": uid.decode(),
                            "folder": "INBOX",
                            "uid_validity": validity,
                        },
                    )
                    with self.store.db() as db:
                        known = db.execute(
                            "SELECT 1 FROM meta WHERE key=?", ("inspected:" + ident,)
                        ).fetchone()
                    if not known:
                        message = self.mail.message(inbox, uid.decode())
                        for index, report in enumerate(
                            message.get("delivery_reports", [])
                        ):
                            kind = {
                                "failed": "message.bounced",
                                "delayed": "message.delayed",
                                "delivered": "message.delivered",
                            }[report["action"]]
                            self.store.event(
                                inbox["id"],
                                kind,
                                ident + ":" + str(index),
                                {"uid": uid.decode(), "status": report["status"]},
                            )
                        with self.store.db() as db:
                            db.execute(
                                "INSERT OR IGNORE INTO meta VALUES(?,?)",
                                ("inspected:" + ident, "1"),
                            )
                    if self.config.workflow:
                        draft = {
                            "body_text": "Thanks for your email. I’ll take a look and get back to you.",
                            "reply_uid": uid.decode(),
                            "folder": "INBOX",
                            "requires_approval": True,
                        }
                        with self.store.db() as db:
                            db.execute(
                                "INSERT OR IGNORE INTO drafts VALUES(?,?,?,?,?)",
                                (
                                    ident,
                                    inbox["id"],
                                    ident,
                                    self.store.seal(draft, ident),
                                    self.store.clock(),
                                ),
                            )
            except Exception:
                self.store.audit("worker", "mail.poll", inbox["id"], "mail_unavailable")

    def run(self):
        lock = (Path(self.config.state) / "worker.lock").open("w")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.recover()
        last = 0
        while True:
            self.job()
            self.webhook()
            if time.monotonic() - last > 15:
                self.poll()
                last = time.monotonic()
            time.sleep(1)


if __name__ == "__main__":
    from .config import Config
    from .store import Store
    from .mail import Mail

    c = Config.load()
    s = Store(c.state)
    Worker(c, s, Mail(c, s)).run()
