"""Build the release downloads from this repository (for maintainers).

    python tools/build_release.py                 writes them into dist/
    python tools/build_release.py --outdir DIR    writes them somewhere else (the installer tests use this)

Makes two files, both for the release's Assets:
  guarded-explore-<version>-windows.zip   everything a user needs, in one folder: install.cmd and uninstall.cmd to
                                          double-click, install.py, the agent, the guard, the tests, the self-check
                                          and the docs
  guarded-explore-setup-<version>.py      a one-file installer: install.py with the agent and the guard built in
The version comes from VERSION in install.py.
"""
from __future__ import annotations

import base64
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE = ["README.md", "LICENSE", "install.cmd", "uninstall.cmd", "install.py", "agents/Explore.md",
           "hooks/explore_shell_guard.py", "tests/test_shell_guard.py", "tests/test_installer.py",
           "tools/check_install.py", "tools/build_release.py", "docs/RESULTS.md", "docs/GUARD.md", "docs/LESSONS.md"]


def build(outdir: Path) -> list:
    installer = (REPO / "install.py").read_text(encoding="utf-8")
    version = re.search(r'^VERSION = "([^"]+)"', installer, re.M).group(1)
    outdir.mkdir(parents=True, exist_ok=True)

    payload = {"agent": base64.b64encode((REPO / "agents" / "Explore.md").read_bytes()).decode("ascii"),
               "guard": base64.b64encode((REPO / "hooks" / "explore_shell_guard.py").read_bytes()).decode("ascii")}
    marker = "PAYLOAD = None"
    if installer.count(marker) != 1:
        raise SystemExit("install.py should hold exactly one 'PAYLOAD = None' line")
    one_file = installer.replace(marker, "PAYLOAD = " + repr(payload), 1)
    one_file = one_file.replace('"""Install or remove the Guarded Explore agent',
                                '"""One-file installer (the agent and the guard are built in). Install or remove the '
                                'Guarded Explore agent', 1)
    setup = outdir / f"guarded-explore-setup-{version}.py"
    one_file = one_file.replace("python install.py", f"python {setup.name}")  # the usage lines name this file
    setup.write_bytes(one_file.encode("utf-8"))

    package = outdir / f"guarded-explore-{version}-windows.zip"
    top = f"guarded-explore-{version}"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in PACKAGE:
            z.write(REPO / rel, f"{top}/{rel}")
    return [package, setup]


def main() -> int:
    outdir = Path(sys.argv[sys.argv.index("--outdir") + 1]) if "--outdir" in sys.argv else REPO / "dist"
    for path in build(outdir):
        print(f"{path}  ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
