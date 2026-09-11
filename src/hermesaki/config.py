import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    mode: str = "development"
    state: str = "/state"
    mail_host: str = "mail"
    mail_port: int = 993
    smtp_port: int = 465
    management_url: str = "https://mail:443"
    ca_file: str = "/state/tls/ca.pem"
    domain: str = "example.test"
    webmail_url: str = ""
    public_url: str = "http://localhost:19100"
    access_team: str = ""
    access_aud: str = ""
    dev_auth: bool = False
    webhook_hosts: list = field(default_factory=list)
    max_attempts: int = 5
    max_message_bytes: int = 5 * 1024 * 1024
    workflow: bool = True

    def validate(self):
        if self.mode not in ("development", "production", "test"):
            raise ValueError("invalid mode")
        if self.mode == "production":
            if self.dev_auth or self.domain.endswith((".test", ".localhost")):
                raise ValueError("development identity/domain forbidden in production")
            if not self.public_url.startswith(
                "https://"
            ) or not self.management_url.startswith("https://"):
                raise ValueError("production requires HTTPS")
            if not re.fullmatch(r"[a-z0-9-]+", self.access_team) or not self.access_aud:
                raise ValueError(
                    "production requires Cloudflare Access team and audience"
                )
        if not 1 <= self.max_attempts <= 20:
            raise ValueError("invalid retry limit")
        return self

    @classmethod
    def load(cls):
        path = Path(os.environ.get("HERMESAKI_CONFIG", "/state/config.json"))
        return cls(**json.loads(path.read_text())).validate()
