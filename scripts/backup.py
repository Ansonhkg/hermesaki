#!/usr/bin/env python3
"""Offline encrypted snapshots. Restore only into a new, empty directory."""

import argparse
import base64
import io
import os
import posixpath
import secrets
import subprocess
import tarfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def pack(source, key):
    if sum(f.stat().st_size for f in Path(source).rglob("*") if f.is_file()) > 1024**3:
        raise ValueError(
            "snapshot exceeds 1 GiB memory-safe limit; use a streaming volume backup"
        )
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        tar.add(source, arcname="state")
    nonce = secrets.token_bytes(12)
    return (
        b"HERMESAKI1"
        + nonce
        + AESGCM(key).encrypt(nonce, out.getvalue(), b"HERMESAKI1")
    )


def unpack(blob, key, destination):
    dest = Path(destination)
    if dest.exists() and any(dest.iterdir()):
        raise ValueError(
            "restore destination must be empty; current state is never overwritten"
        )
    if blob[:10] != b"HERMESAKI1":
        raise ValueError("invalid backup")
    data = AESGCM(key).decrypt(blob[10:22], blob[22:], b"HERMESAKI1")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for m in tar.getmembers():
            if (
                m.islnk()
                or not (m.isfile() or m.isdir() or m.issym())
                or not (m.name == "state" or m.name.startswith("state/"))
                or ".." in Path(m.name).parts
            ):
                raise ValueError("unsafe archive entry")
            if m.issym():
                target = posixpath.normpath(posixpath.join(posixpath.dirname(m.name), m.linkname))
                if posixpath.isabs(m.linkname) or not target.startswith("state/"):
                    raise ValueError("unsafe archive link")
        dest.mkdir(parents=True, exist_ok=True)
        tar.extractall(dest, filter="data")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["backup", "restore"])
    ap.add_argument("archive")
    ap.add_argument("--key-file", required=True)
    ap.add_argument("--state", default=".runtime")
    ap.add_argument("--destination")
    ap.add_argument("--compose", default="compose.yaml")
    args = ap.parse_args()
    keyfile = Path(args.key_file)
    if args.action == "backup":
        if not keyfile.exists():
            fd = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(base64.b64encode(secrets.token_bytes(32)).decode())
        key = base64.b64decode(keyfile.read_text())
        subprocess.run(["docker", "compose", "-f", args.compose, "stop"], check=True)
        try:
            blob = pack(Path(args.state), key)
            fd = os.open(args.archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(blob)
        finally:
            subprocess.run(
                ["docker", "compose", "-f", args.compose, "start"], check=True
            )
    else:
        if not args.destination:
            ap.error("--destination required")
        unpack(
            Path(args.archive).read_bytes(),
            base64.b64decode(keyfile.read_text()),
            args.destination,
        )
    print(args.action + " complete")


if __name__ == "__main__":
    main()
