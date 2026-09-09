"""Rehearse fresh provisioning without modifying the current runtime or live mail."""

import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="hermesaki-clean-") as temp:
    dest = Path(temp) / "repo"
    shutil.copytree(
        root,
        dest,
        ignore=shutil.ignore_patterns(
            ".git", ".runtime*", ".venv", "node_modules", "__pycache__", ".ruff_cache"
        ),
    )
    (dest / ".venv").symlink_to(root / ".venv", target_is_directory=True)
    (dest / "compose.override.yaml").write_text(
        "services:\n  edge:\n    ports: !override\n      - '127.0.0.1:19130:8000'\n      - '127.0.0.1:19131:8080'\n      - '127.0.0.1:19132:8025'\n"
    )
    env = dict(os.environ, COMPOSE_PROJECT_NAME="hermesaki-clean")

    def run(args):
        subprocess.run(args, cwd=dest, env=env, check=True)

    try:
        run([str(root / ".venv/bin/python"), "scripts/dev.py"])
        run(
            [
                "docker",
                "compose",
                "run",
                "--rm",
                "api",
                "python",
                "-m",
                "hermesaki.seed",
            ]
        )
        # The independent clean instance has its own credentials and captured mail.
        client_env = dict(
            os.environ,
            HERMESAKI_URL="http://localhost:19130",
            HERMESAKI_ADMIN_FILE=str(dest / ".runtime/product/operator-token"),
            HERMESAKI_CAPTURE_URL="http://localhost:19132",
        )
        for attempt in range(30):
            try:
                with urllib.request.urlopen(
                    "http://localhost:19130/healthz", timeout=2
                ) as response:
                    if response.status == 200:
                        break
            except OSError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("clean API did not become ready")
        for script in ["live.mjs", "browser.mjs"]:
            subprocess.run(
                ["node", "packages/client/test/" + script],
                cwd=root,
                env=client_env,
                check=True,
            )
        run(["docker", "compose", "restart", "mail", "api", "worker"])
        run(["docker", "compose", "restart", "edge"])
        run(
            [
                "docker",
                "compose",
                "run",
                "--rm",
                "api",
                "python",
                "/app/tests/integration.py",
            ]
        )
        print(
            "PASS: fresh isolated provision, real client/browser flows, restart, seed preservation and upstream mail integration"
        )
    except Exception:
        subprocess.run(
            ["docker", "compose", "logs", "--tail", "60", "api", "worker"],
            cwd=dest,
            env=env,
        )
        raise
    finally:
        subprocess.run(["docker", "compose", "down"], cwd=dest, env=env, check=True)
