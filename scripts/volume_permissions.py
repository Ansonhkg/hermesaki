"""The pinned Stalwart image runs as uid/gid 2000 on Linux."""

import subprocess
import sys
from pathlib import Path


def prepare_mail_volumes(root):
    for name in ("mail-data", "mail-etc"):
        (Path(root) / name).mkdir(exist_ok=True)
    if sys.platform == "linux":
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--user",
                "0:0",
                "-v",
                str(Path(root).resolve()) + ":/state",
                "python@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea",
                "python",
                "-c",
                "import os; [os.chown('/state/'+n,2000,2000) for n in ('mail-data','mail-etc')]",
            ],
            check=True,
        )
