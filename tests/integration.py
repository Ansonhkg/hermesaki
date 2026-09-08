"""Run inside the local API container; no real recipients or external services."""

import html
import base64
import http.cookiejar
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from hermesaki.config import Config
from hermesaki.store import Store
from hermesaki.mail import Mail
from hermesaki.seed import seed

c = Config.load()
assert c.mode == "development"
s = Store(c.state)
m = Mail(c, s)
seed()
seed()
accounts = json.loads(Path("/state/accounts.json").read_text())
a = accounts[0]
b = accounts[1]
token = Path("/state/alice-token").read_text()


def request(path, data=None, method=None, headers=None):
    h = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        **(headers or {}),
    }
    r = urllib.request.urlopen(
        urllib.request.Request(
            "http://api:8000" + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers=h,
            method=method,
        ),
        timeout=20,
    )
    return json.load(r)


messages = request("/v1/inboxes/" + a["id"] + "/messages")
welcome = [x for x in messages if x["subject"] == "Welcome to Hermesaki"]
assert len(welcome) == 1
uid = welcome[0]["uid"]
msg = request("/v1/inboxes/" + a["id"] + "/messages/" + uid)
assert base64.b64decode(msg["attachments"][0]["data"]) == b"fictional attachment\n"
for tool, args in [
    ("list_folders", {}),
    ("search_messages", {"query": "Welcome"}),
    ("read_message", {"uid": uid}),
    ("get_attachment", {"uid": uid, "attachment_id": "0"}),
]:
    r = request(
        "/mcp",
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": {"inbox_id": a["id"], **args}},
        },
    )
    assert "result" in r, r
try:
    request("/v1/inboxes/" + b["id"] + "/messages")
    raise AssertionError("cross mailbox allowed")
except urllib.error.HTTPError as e:
    assert e.code == 403
job = request(
    "/v1/inboxes/" + a["id"] + "/messages",
    {
        "to": ["outside@example.org"],
        "subject": "Captured integration mail",
        "body_text": "This must remain local.",
    },
    headers={"Idempotency-Key": "local-capture-integration"},
)
for _ in range(40):
    with s.db() as db:
        row = db.execute("SELECT state FROM jobs WHERE id=?", (job["id"],)).fetchone()
    if row["state"] != "queued" and row["state"] != "sending":
        break
    time.sleep(1)
assert row["state"] == "submitted", dict(row)
for _ in range(30):
    capture = json.load(urllib.request.urlopen("http://capture:8025/api/v1/messages"))
    if any(x["Subject"] == "Captured integration mail" for x in capture["messages"]):
        break
    time.sleep(1)
else:
    raise AssertionError("message not captured")
# Real SMTP submission to a second local mailbox, followed by IMAP read.
content = {
    "to": [b["email"]],
    "subject": "Local SMTP integration",
    "body_text": "hello bob",
}
m.send(s.inbox(a["id"]), content, "<local-integration@example.test>")
for _ in range(30):
    if m.messages(s.inbox(b["id"]), query="Local SMTP integration"):
        break
    time.sleep(1)
else:
    raise AssertionError("local delivery failed")
# Webmail authentication goes through the real login form and cookie session.
jar = http.cookiejar.CookieJar()
browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
page = browser.open("http://webmail/").read().decode()
csrf = re.search(r'name="_token" value="([^"]+)"', page).group(1)
form = urllib.parse.urlencode(
    {
        "_token": csrf,
        "_task": "login",
        "_action": "login",
        "_user": a["email"],
        "_pass": s.open(s.inbox(a["id"])["secret"], a["id"]),
        "_timezone": "UTC",
        "_url": "",
    }
).encode()
page = browser.open("http://webmail/", form).read().decode()
assert '"task":"mail"' in page or "task=logout" in page or '"task": "mail"' in page, (
    "webmail login failed"
)
assert "login-form" not in page


# Exercise Roundcube's actual compose and reply forms, not just the mail adapter.
def compose(client, recipient, subject, body, reply_uid=None):
    url = "http://webmail/?_task=mail&_action=compose"
    if reply_uid:
        url += "&_reply_uid=" + reply_uid + "&_mbox=INBOX"
    page = client.open(url).read().decode()
    fields = {
        k: html.unescape(v)
        for k, v in re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page)
    }
    identity = re.search(
        r'<select name="_from".*?<option value="([^"]+)"', page, re.S
    ).group(1)
    fields.update(
        _task="mail",
        _action="send",
        _from=identity,
        _to=recipient,
        _subject=subject,
        _message=body,
        _is_html="0",
        _framed="1",
        _store_target="Sent Items",
    )
    client.open(
        "http://webmail/?_task=mail", urllib.parse.urlencode(fields).encode()
    ).read()


web_subject = "Roundcube compose " + str(time.time_ns())
compose(
    browser,
    b["email"],
    web_subject,
    "Sent from the real webmail form.",
)
for _ in range(30):
    candidates = [
        x for x in m.messages(s.inbox(b["id"])) if x["subject"] == web_subject
    ]
    if candidates:
        break
    time.sleep(1)
else:
    raise AssertionError("Roundcube compose did not deliver")
bob_browser = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
)
page = bob_browser.open("http://webmail/").read().decode()
csrf = re.search(r'name="_token" value="([^"]+)"', page).group(1)
bob_browser.open(
    "http://webmail/",
    urllib.parse.urlencode(
        {
            "_token": csrf,
            "_task": "login",
            "_action": "login",
            "_user": b["email"],
            "_pass": s.open(s.inbox(b["id"])["secret"], b["id"]),
        }
    ).encode(),
).read()
compose(
    bob_browser,
    a["email"],
    "Re: " + web_subject,
    "A reply from Bob.",
    candidates[0]["uid"],
)
for _ in range(30):
    replies = [
        x for x in m.messages(s.inbox(a["id"])) if x["subject"] == "Re: " + web_subject
    ]
    if replies:
        break
    time.sleep(1)
else:
    raise AssertionError("Roundcube reply did not arrive")

# Signed delivery to a real local HTTP receiver.
receiver = Path("/state/receiver")
receiver.mkdir(exist_ok=True)
hook = request("/v1/inboxes/" + a["id"] + "/webhooks", {"url": "http://receiver:8090/"})
(receiver / "secret").write_text(hook["secret"])
event = s.event(
    a["id"],
    "message.received",
    "webhook-integration-" + str(time.time_ns()),
    {"uid": uid},
)
for _ in range(30):
    log = receiver / "events.jsonl"
    if log.exists() and any(
        json.loads(x)["id"] == event for x in log.read_text().splitlines()
    ):
        break
    time.sleep(1)
else:
    raise AssertionError("signed webhook not received")
with s.db() as db:
    db.execute("UPDATE hooks SET active=0 WHERE id=?", (hook["id"],))
# The workflow creates drafts, but never sends one automatically.
for _ in range(30):
    drafts = request("/v1/inboxes/" + a["id"] + "/drafts")
    if drafts:
        break
    time.sleep(1)
assert drafts and drafts[0]["requires_approval"]
try:
    request("/v1/inboxes/" + a["id"] + "/drafts/" + drafts[0]["id"] + "/send", {})
    raise AssertionError("draft sent without approval")
except urllib.error.HTTPError as e:
    assert e.code == 400
print(
    "PASS: repeatable seed, TLS IMAP attachment, MCP reads, mailbox isolation, SMTP capture and local delivery, Roundcube login, signed HTTP webhook, draft approval gate"
)
