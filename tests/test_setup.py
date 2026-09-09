import io
import json
import secrets
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from hermesaki.setup import Setup, App, Rejected


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.setup = Setup(self.temp.name)
        self.bootstrap = (Path(self.temp.name) / "bootstrap-token").read_text()
        self.owner = secrets.token_urlsafe(32)

    def claim(self):
        return self.setup.call("POST", "/v1/setup/claim", self.bootstrap, {"owner_token": self.owner})

    def test_claim_once_and_resume_with_saved_owner(self):
        with self.assertRaises(Rejected):
            self.setup.call("POST", "/v1/setup/claim", "wrong", {"owner_token": self.owner})
        self.claim()
        self.assertFalse((Path(self.temp.name) / "bootstrap-token").exists())
        with self.assertRaises(Rejected) as error:
            self.claim()
        self.assertEqual(error.exception.status, 409)
        restarted = Setup(self.temp.name)
        self.assertFalse((Path(self.temp.name) / "bootstrap-token").exists())
        self.assertEqual(restarted.call("GET", "/v1/setup", self.owner, {})["state"], "configuration_required")
        with self.assertRaises(Rejected):
            restarted.call("GET", "/v1/setup", self.bootstrap, {})
        self.assertNotIn(self.owner.encode(), self.setup.database.read_bytes())

    def test_concurrent_claim_has_one_owner(self):
        def attempt(owner):
            try:
                self.setup.call("POST", "/v1/setup/claim", self.bootstrap, {"owner_token": owner})
                return True
            except Rejected:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(attempt, [self.owner, secrets.token_urlsafe(32)])), 1)

    def test_configuration_is_validated_persistent_and_never_marks_complete(self):
        self.claim()
        settings = {"domain": "example.com", "server_ip": "203.0.113.10", "owner_email": "owner@example.com"}
        for invalid in [dict(settings, domain="../oops"), dict(settings, server_ip="bad"), dict(settings, owner_email="bad"), dict(settings, password="secret")]:
            with self.assertRaises(Rejected):
                self.setup.call("PUT", "/v1/setup/configuration", self.owner, invalid)
        first = self.setup.call("PUT", "/v1/setup/configuration", self.owner, settings)
        self.assertEqual(first, self.setup.call("PUT", "/v1/setup/configuration", self.owner, settings))
        result = Setup(self.temp.name).call("GET", "/v1/setup", self.owner, {})
        self.assertEqual(result["settings"], settings)
        self.assertFalse(result["complete"])
        self.assertTrue(all(x["state"] == "pending" for x in result["checks"]))
        with self.assertRaises(Rejected):
            self.setup.call("POST", "/v1/setup/apply", self.owner, {})

    def http(self, **overrides):
        env = {"HTTP_HOST":"127.0.0.1:19200", "REQUEST_METHOD":"GET", "PATH_INFO":"/v1/setup/status", "wsgi.input":io.BytesIO(b'')}
        env.update(overrides)
        status=[]
        body=b''.join(App(self.setup)(env, lambda code, headers: status.append(code)))
        return status[0], body

    def test_http_rejects_cross_origin_host_and_unauthenticated_reads(self):
        self.assertTrue(self.http(HTTP_HOST="evil.example")[0].startswith("403"))
        self.assertTrue(self.http(HTTP_ORIGIN="https://evil.example")[0].startswith("403"))
        self.assertTrue(self.http(PATH_INFO="/v1/setup")[0].startswith("401"))
        self.assertTrue(self.http(CONTENT_LENGTH="20000")[0].startswith("413"))
        self.assertTrue(self.http(CONTENT_LENGTH="1", **{"wsgi.input":io.BytesIO(b'{')})[0].startswith("400"))
        status, body=self.http(PATH_INFO="/")
        self.assertTrue(status.startswith("200"))
        self.assertIn(b"Set up Hermesaki", body)
        self.assertNotIn(self.bootstrap.encode(), body)


if __name__ == "__main__":
    unittest.main()
