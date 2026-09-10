import base64
import concurrent.futures
import hashlib
import hmac
import json
import secrets
import smtplib
import tempfile
import unittest
from pathlib import Path
from hermesaki.config import Config
from hermesaki.store import Store, Problem
from hermesaki.service import Service
from hermesaki.worker import Worker, verify_signature, target
from hermesaki.http import App


class Mail:
    def __init__(self):
        self.sent = []
        self.deleted = []
        self.failure = None

    def send(self, i, c, m):
        if self.failure:
            raise self.failure
        self.sent.append((i, c, m))

    def message(self, *a, **k):
        return {
            "from": "sender@example.test",
            "subject": "hello",
            "message_id": "<original@example.test>",
            "references": "",
            "attachments": [{"id": "0", "data": "aGk="}],
            "body_text": "hi",
        }

    def folders(self, *a):
        return ["INBOX"]

    def messages(self, *a, **k):
        return [{"uid": "1"}]

    def delete(self, *a):
        self.deleted.append(a)


class Product(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        Path(self.tmp.name, "key").write_text(
            base64.b64encode(secrets.token_bytes(32)).decode()
        )
        self.now = 1000
        self.c = Config(
            mode="test", state=self.tmp.name, webhook_hosts=["receiver"], max_attempts=3
        )
        self.s = Store(self.tmp.name, lambda: self.now)
        self.m = Mail()
        self.svc = Service(self.c, self.s, self.m)
        self.admin = {"id": "root", "scopes": ["admin"]}
        self.a = self.svc.create_inbox(self.admin, "alice@example.test")["id"]
        self.b = self.svc.create_inbox(self.admin, "bob@example.test")["id"]
        self.raw = self.s.token(self.a, ["mail.read", "mail.write", "mail.delete"])
        self.actor = self.s.auth(self.raw["token"])
        self.worker = Worker(self.c, self.s, self.m)
        self.content = {
            "to": ["bob@example.test"],
            "subject": "test",
            "body_text": "private body",
        }

    def test_import_existing_mailbox_verifies_and_keeps_identity(self):
        from unittest.mock import Mock
        self.m.verify_credentials = Mock()
        first = self.svc.import_inbox(self.admin, "alice@example.test", "existing-password")
        self.assertEqual(first["id"], self.a)
        self.m.verify_credentials.assert_called_once_with("alice@example.test", "existing-password")
        row = self.s.inbox(self.a)
        self.assertEqual(self.s.open(row["secret"], self.a), "existing-password")
        with self.assertRaises(Problem):
            self.svc.import_inbox(self.actor, "alice@example.test", "other-password")
        self.m.verify_credentials.side_effect = Problem(400, "mailbox_credentials_not_verified")
        with self.assertRaises(Problem):
            self.svc.import_inbox(self.admin, "alice@example.test", "bad-password")
        self.assertEqual(self.s.open(self.s.inbox(self.a)["secret"], self.a), "existing-password")

    def test_onboarding_routes(self):
        app = App(self.svc)
        settings = app.route(self.admin, "GET", ["v1", "settings"], {}, {}, {})
        self.assertEqual(settings["domain"], "example.test")
        with self.assertRaises(Problem):
            app.route(self.actor, "GET", ["v1", "settings"], {}, {}, {})
        route = ["v1", "inboxes", self.a, "test-message"]
        with self.assertRaises(Problem):
            app.route(
                self.admin, "POST", route, {}, {}, {"HTTP_IDEMPOTENCY_KEY": "test"}
            )
        self.c.mode = "development"
        first = app.route(
            self.admin, "POST", route, {}, {}, {"HTTP_IDEMPOTENCY_KEY": "test"}
        )
        second = app.route(
            self.admin, "POST", route, {}, {}, {"HTTP_IDEMPOTENCY_KEY": "test"}
        )
        self.assertEqual(first["id"], second["id"])
        with self.assertRaises(Problem):
            app.route(
                self.actor, "POST", route, {}, {}, {"HTTP_IDEMPOTENCY_KEY": "test"}
            )

    def test_auth(self):
        ro = self.s.auth(self.s.token(self.a, ["mail.read"])["token"])
        with self.assertRaises(Problem):
            self.svc.send(ro, self.a, self.content, "a")
        with self.assertRaises(Problem):
            self.svc.read(self.actor, self.b, "folders")
        short = self.s.token(self.a, ["mail.read"], 1)
        self.now += 2
        with self.assertRaises(Problem):
            self.s.auth(short["token"])
        self.svc.revoke(self.admin, self.raw["id"])
        with self.assertRaises(Problem):
            self.s.auth(self.raw["token"])

    def test_concurrent_idempotency(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            r = list(
                pool.map(
                    lambda _: self.svc.send(self.actor, self.a, self.content, "same"),
                    range(12),
                )
            )
        self.assertEqual(1, len({x["id"] for x in r}))
        self.worker.job()
        self.worker.job()
        self.assertEqual(1, len(self.m.sent))
        with self.assertRaises(Problem):
            self.svc.send(
                self.actor, self.a, self.content | {"subject": "different"}, "same"
            )

    def test_crash(self):
        job = self.svc.send(self.actor, self.a, self.content, "crash")
        with self.s.db() as d:
            d.execute("UPDATE jobs SET state='sending' WHERE id=?", (job["id"],))
        self.worker.recover()
        self.assertFalse(self.worker.job())
        self.assertEqual(
            "uncertain", self.svc.overview(self.admin, "jobs")["items"][0]["state"]
        )

    def test_temporary_rejection(self):
        self.svc.send(self.actor, self.a, self.content, "retry")
        self.m.failure = smtplib.SMTPDataError(451, b"wait")
        self.worker.job()
        self.assertEqual(
            "queued", self.svc.overview(self.admin, "jobs")["items"][0]["state"]
        )
        self.now += 100
        self.m.failure = None
        self.worker.job()
        self.assertEqual(1, len(self.m.sent))

    def test_permanent_bounce(self):
        self.svc.send(self.actor, self.a, self.content, "bounce")
        self.m.failure = smtplib.SMTPDataError(550, b"rejected")
        self.worker.job()
        self.assertEqual(
            "failed", self.svc.overview(self.admin, "jobs")["items"][0]["state"]
        )

    def test_timeout_uncertain(self):
        self.svc.send(self.actor, self.a, self.content, "outage")
        self.m.failure = TimeoutError()
        self.worker.job()
        self.worker.recover()
        self.assertFalse(self.worker.job())

    def test_reply_and_confirmation(self):
        self.svc.send(self.actor, self.a, {"body_text": "reply"}, "reply", "1")
        self.worker.job()
        self.assertEqual("<original@example.test>", self.m.sent[0][1]["in_reply_to"])
        c = self.svc.confirmation(self.actor, self.a, "1", "INBOX")["confirmation"]
        self.now += 61
        with self.assertRaises(Problem):
            self.svc.delete(self.actor, self.a, "1", "INBOX", c)
        c = self.svc.confirmation(self.actor, self.a, "1", "INBOX")["confirmation"]
        self.svc.delete(self.actor, self.a, "1", "INBOX", c)
        with self.assertRaises(Problem):
            self.svc.delete(self.actor, self.a, "1", "INBOX", c)
        self.assertEqual(1, len(self.m.deleted))

    def test_events_webhook_retries(self):
        with self.s.db() as d:
            d.execute(
                "INSERT INTO hooks VALUES(?,?,?,?,1)",
                ("h", self.a, "http://receiver/", self.s.seal("secret", "h")),
            )
        e = self.s.event(self.a, "message.received", "fixed", {"uid": "1"})
        self.assertEqual(
            e, self.s.event(self.a, "message.received", "fixed", {"uid": "1"})
        )

        def fail(*a):
            raise TimeoutError()

        self.worker.sender = fail
        for _ in range(3):
            self.worker.webhook()
            self.now += 100
        row = self.svc.overview(self.admin, "deliveries")["items"][0]
        self.assertEqual("dead", row["state"])
        self.assertEqual(3, row["attempts"])
        self.assertFalse(self.worker.webhook())

    def test_signature(self):
        body = b"{}"
        sig = "v1=" + hmac.new(b"secret", b"1000." + body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_signature(body, "1000", sig, "secret", 1000))
        self.assertFalse(verify_signature(b"x", "1000", sig, "secret", 1000))
        self.assertFalse(verify_signature(body, "1000", sig, "secret", 2000))

    def test_prod_guards(self):
        with self.assertRaises(ValueError):
            Config(mode="production", dev_auth=True).validate()
        with self.assertRaises(Problem):
            target("http://169.254.169.254/", self.c)

    def test_no_body_in_operator_or_plain_db(self):
        self.svc.send(self.actor, self.a, self.content, "private")
        self.assertNotIn(
            "private body", json.dumps(self.svc.overview(self.admin, "jobs"))
        )
        self.assertNotIn(
            b"private body", Path(self.tmp.name, "product.sqlite").read_bytes()
        )

    def test_mcp_scope_denial(self):
        app = App(self.svc)
        ro = self.s.auth(self.s.token(self.a, ["mail.read"])["token"])
        with self.assertRaises(Problem):
            app.mcp(
                ro,
                {
                    "method": "tools/call",
                    "params": {
                        "name": "send_message",
                        "arguments": {
                            "inbox_id": self.a,
                            **self.content,
                            "idempotency_key": "forbidden",
                        },
                    },
                },
            )
        r = app.mcp(
            ro,
            {
                "method": "tools/call",
                "params": {
                    "name": "get_attachment",
                    "arguments": {"inbox_id": self.a, "uid": "1", "attachment_id": "0"},
                },
            },
        )
        self.assertIn("aGk=", r["content"][0]["text"])

    def test_out_of_order_and_duplicate_events(self):
        first = self.s.event(
            self.a, "message.delivered", "delivery", {"job_id": "fixture"}
        )
        self.now += 30
        self.s.event(self.a, "message.submitted", "submission", {"job_id": "fixture"})
        self.assertEqual(
            first,
            self.s.event(
                self.a, "message.delivered", "delivery", {"job_id": "fixture"}
            ),
        )
        self.assertEqual(2, len(self.svc.overview(self.admin, "events")["items"]))

    def test_delete_inbox_confirmation_and_revocation(self):
        app = App(self.svc)
        with self.assertRaises(Problem):
            app.route(
                self.admin,
                "DELETE",
                ["v1", "inboxes", self.a],
                {"confirm_email": "wrong"},
                {},
                {},
            )
        app.route(
            self.admin,
            "DELETE",
            ["v1", "inboxes", self.a],
            {"confirm_email": "alice@example.test"},
            {},
            {},
        )
        with self.assertRaises(Problem):
            self.s.auth(self.raw["token"])

    def test_browser_entry_routes_lead_to_real_sign_in(self):
        app = App(self.svc)
        for path in ("/onboarding", "/ui/", "/ui/onboarding/", "/ui/onboarding/index.html"):
            responses = []
            app({"PATH_INFO": path, "REQUEST_METHOD": "GET"}, lambda st, h: responses.append((st, dict(h))))
            self.assertEqual(responses[0][0], "303 See Other")
            self.assertEqual(responses[0][1]["Location"], "/ui/onboarding/live.html")

    def test_http_requires_auth(self):
        statuses = []
        app = App(self.svc)
        body = b"".join(
            app(
                {"PATH_INFO": "/v1/operator/jobs", "REQUEST_METHOD": "GET"},
                lambda st, h: statuses.append(st),
            )
        )
        self.assertTrue(statuses[0].startswith("401"))
        self.assertIn(b"token_required", body)


if __name__ == "__main__":
    unittest.main()
