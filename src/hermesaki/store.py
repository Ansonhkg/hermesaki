import base64
import hashlib
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class Problem(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


class Store:
    def __init__(self, state, clock=time.time):
        self.path = Path(state)
        self.path.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.cipher = AESGCM(base64.b64decode((self.path / "key").read_text().strip()))
        with self.db() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS inboxes(id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, secret TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS tokens(id TEXT PRIMARY KEY, hash TEXT UNIQUE NOT NULL, inbox TEXT, scopes TEXT NOT NULL, expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, inbox TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS hooks(id TEXT PRIMARY KEY, inbox TEXT NOT NULL, url TEXT NOT NULL, secret TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS deliveries(id TEXT PRIMARY KEY, hook TEXT NOT NULL, event TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, due REAL NOT NULL, lease TEXT, error TEXT, UNIQUE(hook,event));
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, inbox TEXT NOT NULL, idem TEXT NOT NULL, fingerprint TEXT NOT NULL, message TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, due REAL NOT NULL, message_id TEXT NOT NULL, error TEXT, lease TEXT, UNIQUE(inbox,idem));
            CREATE TABLE IF NOT EXISTS confirmations(hash TEXT PRIMARY KEY, inbox TEXT NOT NULL, action TEXT NOT NULL, expires REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY, inbox TEXT NOT NULL, event TEXT UNIQUE NOT NULL, content TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, resource TEXT, result TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
            """)
            db.execute("INSERT OR IGNORE INTO meta VALUES('schema','1')")
            if (
                db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()[0]
                != "1"
            ):
                raise RuntimeError("unsupported database schema")

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path / "product.sqlite", timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def seal(self, value, context):
        nonce = secrets.token_bytes(12)
        return base64.b64encode(
            nonce
            + self.cipher.encrypt(nonce, json.dumps(value).encode(), context.encode())
        ).decode()

    def open(self, value, context):
        raw = base64.b64decode(value)
        return json.loads(self.cipher.decrypt(raw[:12], raw[12:], context.encode()))

    def token(self, inbox, scopes, ttl=2592000):
        allowed = {"mail.read", "mail.write", "mail.delete", "admin"}
        if (
            not set(scopes) <= allowed
            or not scopes
            or (inbox is not None and "admin" in scopes)
        ):
            raise Problem(400, "invalid_scopes")
        raw = secrets.token_urlsafe(32)
        ident = secrets.token_hex(12)
        with self.db() as db:
            if (
                inbox is not None
                and not db.execute(
                    "SELECT 1 FROM inboxes WHERE id=? AND active=1", (inbox,)
                ).fetchone()
            ):
                raise Problem(404, "inbox_not_found")
            db.execute(
                "INSERT INTO tokens VALUES(?,?,?,?,?,0)",
                (
                    ident,
                    hashlib.sha256(raw.encode()).hexdigest(),
                    inbox,
                    json.dumps(scopes),
                    self.clock() + ttl,
                ),
            )
        return {"id": ident, "token": raw, "scopes": scopes}

    def auth(self, raw):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM tokens WHERE hash=? AND revoked=0 AND expires>?",
                (hashlib.sha256(raw.encode()).hexdigest(), self.clock()),
            ).fetchone()
        if not row:
            raise Problem(401, "invalid_token")
        return dict(row) | {"scopes": json.loads(row["scopes"])}

    def audit(self, actor, action, resource, result="ok"):
        with self.db() as db:
            db.execute(
                "INSERT INTO audit(actor,action,resource,result,created) VALUES(?,?,?,?,?)",
                (actor, action, resource, result, self.clock()),
            )

    def inbox(self, ident):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM inboxes WHERE id=? AND active=1", (ident,)
            ).fetchone()
        if not row:
            raise Problem(404, "inbox_not_found")
        return dict(row)

    def event(self, inbox, kind, key, data):
        ident = hashlib.sha256((inbox + ":" + kind + ":" + key).encode()).hexdigest()
        payload = {
            "id": ident,
            "version": "1",
            "type": kind,
            "inbox_id": inbox,
            "created_at": self.clock(),
            "data": data,
        }
        with self.db() as db:
            cur = db.execute(
                "INSERT OR IGNORE INTO events VALUES(?,?,?,?,?)",
                (ident, inbox, kind, json.dumps(payload), self.clock()),
            )
            if cur.rowcount:
                for hook in db.execute(
                    "SELECT id FROM hooks WHERE inbox=? AND active=1", (inbox,)
                ).fetchall():
                    db.execute(
                        "INSERT OR IGNORE INTO deliveries(id,hook,event,state,due) VALUES(?,?,?,?,?)",
                        (
                            secrets.token_hex(12),
                            hook["id"],
                            ident,
                            "pending",
                            self.clock(),
                        ),
                    )
        return ident
