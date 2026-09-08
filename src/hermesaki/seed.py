import email.policy
import json
from email.message import EmailMessage
from pathlib import Path
from .config import Config
from .store import Store
from .mail import Mail


def seed():
    c = Config.load()
    if c.mode != "development":
        raise RuntimeError("seed forbidden outside development")
    s = Store(c.state)
    m = Mail(c, s)
    accounts = json.loads((Path(c.state) / "accounts.json").read_text())
    for a in accounts:
        with m.connect(s.inbox(a["id"])) as imap:
            imap.create("Fixtures")
            imap.select("INBOX")
            mid = "<hermesaki-welcome-" + a["id"] + "@example.test>"
            found = any(
                mid.encode() in part[1]
                for uid in (imap.uid("search", None, "ALL")[1][0] or b"").split()
                for part in imap.uid(
                    "fetch", uid, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])"
                )[1]
                if isinstance(part, tuple)
            )
            if found:
                continue
            msg = EmailMessage()
            msg["From"] = "friend@example.test"
            msg["To"] = a["email"]
            msg["Subject"] = "Welcome to Hermesaki"
            msg["Message-ID"] = mid
            msg.set_content("This is fictional local test mail.")
            msg.add_attachment(
                b"fictional attachment\n",
                maintype="text",
                subtype="plain",
                filename="hello.txt",
            )
            status, _ = imap.append(
                "INBOX", None, None, msg.as_bytes(policy=email.policy.SMTP)
            )
            if status != "OK":
                raise RuntimeError("seed failed")
    print(
        "Seed ready: two fictional inboxes, welcome mail and attachment. Existing data preserved."
    )


if __name__ == "__main__":
    seed()
