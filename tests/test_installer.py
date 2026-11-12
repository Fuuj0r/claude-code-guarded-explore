"""Tests for install.py, run in throwaway home folders (never your real one).

    python tests/test_installer.py     (the last line reads "19 of 19 passed")

Covers a fresh install, a re-run, keeping your model choice, replacing an older copy (and keeping it),
uninstall, backing up and restoring someone else's Explore agent, --check changing nothing, the stops
on macOS (simulated) and on a too-old Claude Code (simulated), and the two release downloads: the zip
(its exact contents and line endings) and the one-file installer, each installing on its own.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ZIP_FILES = ["README.md", "LICENSE", "install.cmd", "uninstall.cmd", "install.py", "agents/Explore.md",
             "hooks/explore_shell_guard.py", "tests/test_shell_guard.py", "tests/test_installer.py",
             "tools/check_install.py", "tools/build_release.py", "docs/RESULTS.md", "docs/GUARD.md", "docs/LESSONS.md"]
results = []


def run(home, *args):
    p = subprocess.run([sys.executable, "-I", str(REPO / "install.py"), "--home", str(home), *args],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail[-300:]}]"))


base = Path(tempfile.mkdtemp(prefix="gx-installer-test-"))
try:
    # 1. fresh install
    h = base / "fresh"
    h.mkdir()
    code, out = run(h, "--yes")
    agent, guard = h / ".claude/agents/Explore.md", h / ".claude/hooks/explore_shell_guard.py"
    check("fresh install exits 0 and both files exist", code == 0 and agent.is_file() and guard.is_file(), out)
    check("installed guard passes its tests", "mismatches: 0" in out, out)
    # 2. re-run says already this version
    code, out = run(h, "--check")
    check("re-run reports both files already this version", out.count("already this version") == 2, out)
    # 3a. only the model line edited: the re-install keeps it, and there's nothing else to change
    agent.write_text(re.sub(r"^model:.*$", "model: sonnet", agent.read_text(encoding="utf-8"), flags=re.M),
                     encoding="utf-8")
    code, out = run(h, "--yes")
    check("model-only edit: re-install keeps the user's model", "model: sonnet" in agent.read_text(encoding="utf-8"), out)
    # 3b. an older copy of ours with the user's model: replaced, model kept, the old copy saved
    agent.write_text(agent.read_text(encoding="utf-8") + "\nAn older version's extra line.\n", encoding="utf-8")
    code, out = run(h, "--yes")
    body = agent.read_text(encoding="utf-8")
    check("older copy: replaced, keeping the user's model", "model: sonnet" in body and "older version" not in body, out)
    prev = h / ".claude/guarded-explore-backup/Explore.md.previous"
    check("older copy: a copy of it is kept", prev.is_file() and "older version" in prev.read_text(encoding="utf-8"), out)
    # 4. uninstall removes ours
    code, out = run(h, "--uninstall", "--yes")
    check("uninstall removes the agent and the guard", not agent.exists() and not guard.exists(), out)
    # 5. someone else's Explore is backed up, then put back byte for byte
    h2 = base / "foreign"
    (h2 / ".claude/agents").mkdir(parents=True)
    theirs = h2 / ".claude/agents/Explore.md"
    original = b"---\nname: Explore\ndescription: \"someone else's\"\n---\nbody\n"
    theirs.write_bytes(original)
    code, out = run(h2, "--yes")
    check("someone else's agent is backed up", (h2 / ".claude/guarded-explore-backup/Explore.md").read_bytes() == original, out)
    code, out = run(h2, "--uninstall", "--yes")
    check("uninstall puts theirs back byte for byte", theirs.read_bytes() == original, out)
    # 6. --check changes nothing
    h3 = base / "dry"
    h3.mkdir()
    code, out = run(h3, "--check")
    check("--check changes nothing", not any(h3.rglob("*")), out)
    # 7. the platform gate (simulated)
    h4 = base / "mac"
    h4.mkdir()
    p = subprocess.run([sys.executable, "-I", "-B", "-c",
                        "import sys; sys.argv=['install.py','--home',r'%s','--yes']; sys.platform='darwin'; "
                        "sys.path.insert(0, r'%s'); import install; raise SystemExit(install.main())" % (h4, REPO)],
                       capture_output=True, text=True)
    check("stops on macOS (simulated) and changes nothing", p.returncode == 1 and "Windows only" in p.stdout and
          not any(h4.rglob("*")), p.stdout + p.stderr)
    # 8. the Claude Code version gate (simulated)
    h5 = base / "oldclaude"
    h5.mkdir()
    p = subprocess.run([sys.executable, "-I", "-B", "-c",
                        "import sys; sys.argv=['install.py','--home',r'%s','--yes']; sys.path.insert(0, r'%s'); "
                        "import install; install.claude_version=lambda: (2, 1, 200); raise SystemExit(install.main())"
                        % (h5, REPO)], capture_output=True, text=True)
    check("stops on a too-old Claude Code (simulated) and changes nothing", p.returncode == 1 and "too old" in p.stdout
          and not any(h5.rglob("*")), p.stdout + p.stderr)
    # 9. the release downloads: build them, then install from each on its own, away from this repository
    out = base / "dist"
    b = subprocess.run([sys.executable, "-I", str(REPO / "tools" / "build_release.py"), "--outdir", str(out)],
                       capture_output=True, text=True)
    setup = next(out.glob("guarded-explore-setup-*.py"), None)
    package = next(out.glob("guarded-explore-*-windows.zip"), None)
    check("build_release makes both downloads", b.returncode == 0 and setup is not None and package is not None,
          b.stdout + b.stderr)
    if setup is not None:
        alone = base / "alone"
        alone.mkdir()
        lone = alone / setup.name  # copied alone: no repository files beside it
        shutil.copyfile(setup, lone)
        h6 = base / "onefile"
        h6.mkdir()
        p = subprocess.run([sys.executable, "-I", str(lone), "--home", str(h6), "--yes"], capture_output=True,
                           text=True)
        agent6 = h6 / ".claude/agents/Explore.md"
        check("one-file installer installs both files, identical to the repository's", p.returncode == 0 and
              agent6.read_bytes() == (REPO / "agents/Explore.md").read_bytes() and
              (h6 / ".claude/hooks/explore_shell_guard.py").read_bytes() ==
              (REPO / "hooks/explore_shell_guard.py").read_bytes() and "quick check: 7 of 7" in p.stdout,
              p.stdout + p.stderr)
        p = subprocess.run([sys.executable, "-I", str(lone), "--home", str(h6), "--uninstall", "--yes"],
                           capture_output=True, text=True)
        check("one-file installer uninstalls", p.returncode == 0 and not agent6.exists(), p.stdout + p.stderr)
    if package is not None:
        import zipfile
        unpacked = base / "unpacked"
        with zipfile.ZipFile(package) as z:
            contents = {name: z.read(name) for name in z.namelist()}
            z.extractall(unpacked)
        top = next(iter(contents)).split("/", 1)[0]
        expected = sorted(f"{top}/{rel}" for rel in ZIP_FILES)
        check("the zip holds exactly the 14 expected files, in one folder", sorted(contents) == expected,
              str(sorted(set(contents) ^ set(expected))))

        def endings_ok(name, data):
            if name.endswith(".cmd"):  # cmd.exe needs Windows line endings
                return b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")
            return b"\r" not in data

        bad = [name for name, data in contents.items() if not endings_ok(name, data)]
        check("line endings in the zip: Windows for the .cmd files, Unix for the rest", not bad, str(bad))
        folder = next(unpacked.iterdir())
        h7 = base / "frompackage"
        h7.mkdir()
        p = subprocess.run([sys.executable, "-I", str(folder / "install.py"), "--home", str(h7), "--yes"],
                           capture_output=True, text=True)
        check("the zip's installer installs and passes the full guard tests", p.returncode == 0 and
              "mismatches: 0" in p.stdout and (h7 / ".claude/agents/Explore.md").is_file(), p.stdout + p.stderr)
        check("the zip has install.cmd and uninstall.cmd", (folder / "install.cmd").is_file() and
              (folder / "uninstall.cmd").is_file(), str(list(folder.iterdir())))
finally:
    shutil.rmtree(base, ignore_errors=True)
print(f"{sum(results)} of {len(results)} passed on Python {sys.version.split()[0]}")
