"""Fetch the exact upstream source and apply our reproducible compatibility patch."""

import json
import subprocess
import shutil
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
component = json.loads((root / "components.lock.json").read_text())["mcpcube"]
cache = root / ".cache" / "mcpcube"
fingerprint = hashlib.sha256(
    (root / "components.lock.json").read_bytes()
    + (root / "patches/mcpcube-compatibility.patch").read_bytes()
    + (root / "integrations/mcpcube/composer.lock").read_bytes()
).hexdigest()
marker = cache / ".hermesaki-prepared"
if cache.exists():
    if marker.exists() and marker.read_text() == fingerprint:
        print("Pinned source already prepared.")
        raise SystemExit(0)
    raise SystemExit(
        "Source cache differs or is incomplete. Remove .cache/mcpcube explicitly before preparing again."
    )
cache.parent.mkdir(exist_ok=True)
subprocess.run(["gh", "repo", "clone", component["repository"], str(cache)], check=True)
subprocess.run(
    ["git", "-C", str(cache), "checkout", "--detach", component["revision"]], check=True
)
subprocess.run(
    [
        "git",
        "-C",
        str(cache),
        "apply",
        str(root / "patches/mcpcube-compatibility.patch"),
    ],
    check=True,
)
shutil.copyfile(root / "integrations/mcpcube/composer.lock", cache / "composer.lock")
# The plugin loads this file after its defaults, keeping runtime secrets outside the image.
(cache / "config.inc.php").write_text(
    "<?php\nrequire '/var/roundcube/config/mcp.php';\n"
)
shutil.rmtree(cache / ".git")
marker.write_text(fingerprint)
print("Pinned and patched MCPcube source prepared. Upstream LICENSE retained.")
