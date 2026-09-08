"""Local-only external webhook emulator. Never included in production Compose."""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from .worker import verify_signature

root = Path("/receiver")
root.mkdir(exist_ok=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        if n > 65536:
            self.send_error(413)
            return
        body = self.rfile.read(n)
        if not (root / "secret").exists():
            self.send_error(503)
            return
        valid = verify_signature(
            body,
            self.headers.get("X-Hermesaki-Timestamp"),
            self.headers.get("X-Hermesaki-Signature", ""),
            (root / "secret").read_text(),
            time.time(),
        )
        if not valid:
            self.send_error(401)
            return
        event = json.loads(body)
        with (root / "events.jsonl").open("a") as f:
            f.write(json.dumps({"id": event["id"], "signature_valid": valid}) + "\n")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")


HTTPServer(("0.0.0.0", 8090), Handler).serve_forever()
