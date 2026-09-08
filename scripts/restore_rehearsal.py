"""Restore a complete stopped snapshot into a second isolated Compose project."""

import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from backup import pack, unpack

os.chdir(Path(__file__).resolve().parents[1])
root = Path.cwd()


def dc(*args):
    return subprocess.run(
        ["docker", "compose", *args], check=True, capture_output=True, text=True
    )


with tempfile.TemporaryDirectory(prefix="hermesaki-restore-") as tmp:
    dest = Path(tmp)
    key = secrets.token_bytes(32)
    dc("stop")
    try:
        blob = pack(root / ".runtime", key)
    finally:
        dc("start")
    unpack(blob, key, dest / "restore")
    config = json.loads(dc("config", "--format", "json").stdout)
    config["name"] = "hermesaki-restore"
    for service in config["services"].values():
        service.pop("build", None)
        for volume in service.get("volumes", []):
            source = volume.get("source", "")
            if source.startswith(str(root / ".runtime")):
                volume["source"] = source.replace(
                    str(root / ".runtime"), str(dest / "restore/state"), 1
                )
        for port in service.get("ports", []):
            port["published"] = str(int(port["published"]) + 10)
    for name, network in config["networks"].items():
        network["name"] = "hermesaki-restore_" + name
    conf = dest / "compose.json"
    conf.write_text(json.dumps(config))
    cmd = ["docker", "compose", "-p", "hermesaki-restore", "-f", str(conf)]
    try:
        subprocess.run(cmd + ["up", "-d"], check=True)
        import time

        time.sleep(3)
        subprocess.run(
            cmd + ["run", "--rm", "api", "python", "/app/tests/integration.py"],
            check=True,
        )
        print(
            "PASS: complete encrypted snapshot restored into a separate mail/API/webmail stack"
        )
    finally:
        subprocess.run(cmd + ["down"], check=True)
