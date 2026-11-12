"""Install or remove the Guarded Explore agent for Claude Code (Windows only for now: see the README).

    python install.py               show what it will do, then ask before installing
    python install.py --yes         install without asking
    python install.py --uninstall   remove it, and put back any Explore agent it replaced
    python install.py --check       show what it would do; change nothing

Installing:
  1. copies hooks/explore_shell_guard.py to ~/.claude/hooks/;
  2. copies agents/Explore.md to ~/.claude/agents/. A different Explore agent already there is moved to
     ~/.claude/guarded-explore-backup/ first, and put back by --uninstall. An earlier copy of this one is replaced,
     keeping your model and effort lines, with a copy of it kept in the same backup folder;
  3. tests the installed guard (the full test suite when it's beside this file; otherwise a quick check).
It never edits your CLAUDE.md (the README says when you might add one line). Needs Python 3.9 or later.

tools/build_release.py also makes a one-file version of this installer, with the agent and the guard built in.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = "1.0.0"
PAYLOAD = None  # filled in by tools/build_release.py for the one-file installer: the agent and guard, base64
REPO = Path(__file__).resolve().parent
MIN_CLAUDE = (2, 1, 295)  # the hook's onFailure setting needs this
FORCE = "--force" in sys.argv


def source_agent() -> str:
    if PAYLOAD:  # line endings normalised, so a build from a Windows-style checkout still matches on re-runs
        return base64.b64decode(PAYLOAD["agent"]).decode("utf-8").replace("\r\n", "\n")
    return (REPO / "agents" / "Explore.md").read_text(encoding="utf-8")


def source_guard() -> bytes:
    if PAYLOAD:
        return base64.b64decode(PAYLOAD["guard"])
    return (REPO / "hooks" / "explore_shell_guard.py").read_bytes()


def self_test(guard: Path) -> tuple:
    """(passed, summary) for the installed guard: the full suite if it's here, else a quick check."""
    suite = REPO / "tests" / "test_shell_guard.py"
    if suite.is_file() and not PAYLOAD:
        test = subprocess.run([sys.executable, str(suite), "--guard", str(guard)], capture_output=True, text=True)
        return test.returncode == 0, (test.stdout.strip().splitlines() or ["(no output)"])[-1]
    cases = [("ls -a src", True), ("git log -1 -- a.py", True), ("find . -name '*.py'", True), ("cat .env", False),
             ("echo $(whoami)", False), ("find . -delete", False), ("ls //server/share", False)]
    right = 0
    for command, allowed in cases:
        call = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}).encode()
        p = subprocess.run([sys.executable, str(guard)], input=call, capture_output=True)
        right += (p.returncode == 0) == allowed
    return right == len(cases), f"quick check: {right} of {len(cases)} commands handled as expected"


def home() -> Path:
    if "--home" in sys.argv:  # for testing the installer in a throwaway folder
        return Path(sys.argv[sys.argv.index("--home") + 1]).resolve()
    return Path.home()


def paths() -> dict:
    base = home() / ".claude"
    return {"agent": base / "agents" / "Explore.md", "guard": base / "hooks" / "explore_shell_guard.py",
            "backup": base / "guarded-explore-backup" / "Explore.md",
            "previous": base / "guarded-explore-backup" / "Explore.md.previous"}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def ours(path: Path) -> bool:
    return "explore_shell_guard" in text(path)


def line(name: str, body: str) -> str | None:
    found = re.search(rf"^{name}:\s*(\S+)\s*$", body, re.M)
    return found.group(1) if found else None


def python_name() -> str | None:
    """The command the hook should use: 'python' if that runs Python 3.9 or later, else 'python3'."""
    for name in ("python", "python3"):
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            out = subprocess.run([exe, "-c", "import sys; print(sys.version_info >= (3, 9))"], capture_output=True,
                                 text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        if out.stdout.strip() == "True":
            return name
    return None


def claude_version() -> tuple | None:
    exe = shutil.which("claude")  # the full path also finds a claude.cmd installed through npm
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    found = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(x) for x in found.groups()) if found else None


def ask(question: str) -> bool:
    if "--yes" in sys.argv:
        return True
    try:
        return input(question + " Type y and press Enter: ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def install(dry: bool) -> int:
    print(f"Guarded Explore {VERSION}: install\n")
    if sys.platform != "win32" and not FORCE:
        print("This is Windows only for now. On macOS, Linux and WSL, Claude Code gives a subagent its Grep and Glob\n"
              "tools only if it has no shell, so this agent couldn't search file contents there. Nothing changed.\n"
              "(--force installs anyway, if you're testing a fix.)")
        return 1
    p = paths()
    try:
        new, guard_new = source_agent(), source_guard()
    except FileNotFoundError as missing:
        print(f"Can't find {missing.filename}.\nRun this from the unzipped download folder, or use the one-file "
              "installer from the release page. Nothing changed.")
        return 1
    py = python_name()
    if py == "python3":
        new = new.replace("command: 'python \"$HOME", "command: 'python3 \"$HOME")
    existing, old = p["agent"], text(p["agent"])
    kept = []
    if ours(existing):  # keep the user's own model and effort choices
        for name in ("model", "effort"):
            mine, theirs = line(name, old), line(name, new)
            if mine and theirs and mine != theirs:
                new = re.sub(rf"^{name}:\s*\S+\s*$", f"{name}: {mine}", new, count=1, flags=re.M)
                kept.append(f"{name}: {mine}")

    print(f"- Python for the guard: {py or 'NOT FOUND'}")
    if not py:
        print("  The guard needs Python 3.9 or later on your PATH, as 'python' or 'python3'. Install it, then run this\n"
              "  again. (Without it, the agent's shell is blocked, though it still searches with its other tools.)")
        if not FORCE:
            return 1
    version = claude_version()
    if version is None:
        print("- Claude Code: the 'claude' command isn't on your PATH, so its version can't be checked. That's fine if\n"
              "  you only use the desktop app and keep it up to date; it needs 2.1.295 or later.")
    elif version < MIN_CLAUDE:
        print(f"- Claude Code: {'.'.join(map(str, version))}, too old. The guard's fail-safe needs "
              f"{'.'.join(map(str, MIN_CLAUDE))} or later: update Claude Code first. Nothing changed.")
        if not FORCE:
            return 1
    else:
        print(f"- Claude Code: {'.'.join(map(str, version))}")
    if old == new:
        print(f"- {existing}: already this version")
    elif ours(existing):
        print(f"- {existing}: an earlier or edited copy of this agent; it will be replaced"
              + (f" (keeping {', '.join(kept)})" if kept else "") + f", with a copy kept at {p['previous']}")
    elif existing.is_file():
        if p["backup"].exists():
            print(f"- {existing}: another Explore agent is there, and a backup already exists at {p['backup']}.\n"
                  "  Move one of them yourself, then run this again. Nothing changed.")
            return 1
        print(f"- {existing}: another Explore agent is there; it will be moved to {p['backup']}")
    else:
        print(f"- {existing}: will be created")
    same_guard =p["guard"].is_file() and p["guard"].read_bytes() == guard_new
    print(f"- {p['guard']}: " + ("already this version" if same_guard else
                                 ("will be replaced" if p["guard"].exists() else "will be created")))
    print("- Note: a project's own .claude/agents/Explore.md wins over this one inside that project.")
    if dry:
        print("\nNothing changed (--check).")
        return 0
    if not ask("\nInstall now?"):
        print("Nothing changed.")
        return 0

    # Guard first: if anything later fails, the old agent is still in place.
    p["guard"].parent.mkdir(parents=True, exist_ok=True)
    p["guard"].write_bytes(guard_new)
    moved = None
    try:
        if old and old != new:
            p["backup"].parent.mkdir(parents=True, exist_ok=True)
            moved = p["previous"] if ours(existing) else p["backup"]
            shutil.copyfile(existing, moved)
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(new.encode("utf-8"))
    except OSError as problem:
        print(f"\nCouldn't write the agent file ({problem}). Your earlier file, if any, is unchanged"
              + (f" and also copied to {moved}" if moved else "") + ".")
        return 1
    print("\nInstalled." + (f" Kept your {', '.join(kept)}." if kept else "") + " Testing the installed guard...")
    passed, summary = self_test(p["guard"])
    print(f"  {summary}")
    if not passed:
        print("  The installed guard didn't behave as expected: please open an issue with this output.")
    print("\nNext:\n"
          "  1. Restart Claude Code, or start a new session, so it picks up the agent.\n"
          "  2. Optional, if your CLAUDE.md tells Claude to name a model for every subagent: add the line from the\n"
          "     README, or Explore's own model gets overridden.\n"
          "  3. Optional: tools/check_install.py (in the full download) proves it end to end with one short session.")
    print(f"\nTo remove it later: run {Path(sys.argv[0]).name} again with --uninstall"
          + (", or double-click uninstall.cmd." if (REPO / "uninstall.cmd").is_file() and not PAYLOAD else "."))
    return 0 if passed else 1


def uninstall(dry: bool) -> int:
    p = paths()
    print(f"Guarded Explore {VERSION}: uninstall\n")
    agent = p["agent"]
    mine = ours(agent)
    if mine:
        print(f"- {agent}: will be removed")
    elif agent.is_file():
        print(f"- {agent}: this isn't Guarded Explore, so it's left alone")
    else:
        print(f"- {agent}: not there")
    print(f"- {p['guard']}: {'will be removed' if p['guard'].exists() else 'not there'}")
    slot_free = mine or not agent.exists()
    if p["backup"].is_file():
        print(f"- {p['backup']}: " + ("your earlier Explore agent will be put back" if slot_free else
                                      "your earlier Explore agent stays there, because another one is in place now"))
    if dry:
        print("\nNothing changed (--check).")
        return 0
    if not ask("\nRemove it now?"):
        print("Nothing changed.")
        return 0
    if mine:
        agent.unlink()
    if p["guard"].exists():
        p["guard"].unlink()
    try:
        p["guard"].parent.rmdir()  # only if empty: the hooks folder may hold other hooks
    except OSError:
        pass
    if p["backup"].is_file() and not agent.exists():
        shutil.move(str(p["backup"]), str(agent))
    try:
        p["backup"].parent.rmdir()  # only if empty
    except OSError:
        pass
    print("\nRemoved. Restart Claude Code, or start a new session: it uses the built-in Explore again.")
    return 0


def main() -> int:
    dry = "--check" in sys.argv
    code = uninstall(dry) if "--uninstall" in sys.argv else install(dry)
    # Started by a double-click (no arguments, not from a command prompt): keep the window open to read.
    if (len(sys.argv) == 1 and sys.platform == "win32" and "PROMPT" not in os.environ
            and not os.environ.get("GUARDED_EXPLORE_NO_PAUSE")):  # install.cmd pauses by itself
        try:
            input("\nPress Enter to finish.")
        except EOFError:
            pass
    return code


if __name__ == "__main__":
    sys.exit(main())
