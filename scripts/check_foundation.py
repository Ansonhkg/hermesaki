"""Validate the specification/build foundation. Not the future product test suite."""
import json, re
from pathlib import Path
root = Path(__file__).resolve().parents[1]
lock = json.loads((root / "components.lock.json").read_text())
for name in ("stalwart", "roundcube"):
    assert re.search(r"@sha256:[a-f0-9]{64}$", lock[name]["image"]), name
assert re.fullmatch(r"[a-f0-9]{40}", lock["mcpcube"]["revision"])
criteria = (root / "docs/acceptance.md").read_text()
for group, count in (("A", 15), ("B", 8)):
    for n in range(1, count + 1):
        assert f"| {group}{n:02d} |" in criteria
patch = (root / "patches/mcpcube-compatibility.patch").read_text()
assert "storage_ssl" in patch and "storage_port" in patch and "register(false)" in patch
json.loads((root / "integrations/mcpcube/composer.lock").read_text())
assert not (root / ".github/workflows").exists(), "CI is explicitly out of scope"
print("Foundation checks passed. Product acceptance criteria are still pending.")
