#!/usr/bin/env python3
"""bare.py -- run a gate the way CI will run it, on a machine that has everything.

    python3 scripts/bare.py scripts/test_checks.py
    python3 scripts/bare.py scripts/check_consistency.py

WHY

CI installs nothing: no Pillow, no pcbnew, no kicad-cli. A development machine has all
three, so a gate can pass locally and fail on the runner for a reason no local run can
show you. That happened: check [21] imported fab_package, fab_package imported
render_board at module scope, render_board imports Pillow at module scope, and the whole
suite died on the runner two seconds in -- after a green local run and a merge.

The checks are written to DECLINE with a stated reason when a dependency is missing, which
is the behaviour this exercises. `test_checks.py` counts a declined check separately from a
blind one, so what you want to see here is the same case count as a full run, zero blind,
and warnings naming what was skipped and why.

This blocks the imports rather than uninstalling anything, so it is safe to run at any time
and changes nothing on disk.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

BLOCKED = ("PIL", "pcbnew")
BLOCKED_BINARIES = ("kicad-cli", "kicad")

_SITE = '''
import sys


class _Blocked:
    """Refuse the imports CI does not have, with the same shape as a real ImportError."""

    def find_module(self, name, path=None):
        return self if name.split(".")[0] in %r else None

    def load_module(self, name):
        raise ImportError("not installed on this runner: " + name)


sys.meta_path.insert(0, _Blocked())
'''


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip().split("\\n\\n")[1], file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "sitecustomize.py"), "w").write(_SITE % (BLOCKED,))
        # An empty directory FIRST on PATH cannot hide a binary; shadow each one with a
        # stub that exits non-zero, which is what "not installed" looks like to a check
        # that probes with shutil.which().
        binq = os.path.join(td, "bin")
        os.mkdir(binq)
        for b in BLOCKED_BINARIES:
            p = os.path.join(binq, b)
            open(p, "w").write("#!/bin/sh\\nexit 127\\n")
            os.chmod(p, 0o755)
        env = dict(os.environ)
        env["PYTHONPATH"] = td + os.pathsep + env.get("PYTHONPATH", "")
        env["PATH"] = binq + os.pathsep + env["PATH"]
        print(f"# blocking imports {', '.join(BLOCKED)} and binaries "
              f"{', '.join(BLOCKED_BINARIES)}\\n")
        return subprocess.run([sys.executable] + sys.argv[1:], env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
