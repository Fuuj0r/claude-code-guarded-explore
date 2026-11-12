"""Check the installed Explore agent end to end: one short `claude -p` session, a couple of minutes.

    python tools/check_install.py
    python tools/check_install.py --permission-mode auto     (passed through to claude, if you need it)

It makes a throwaway git repository in your temp folder (a tracked file, a hidden folder and a git-ignored folder),
starts a `claude -p` session there with your normal settings, and has it call Explore once. Then it checks:
  1. Explore ran on the model its own file names (not the calling session's), and no model was passed on the call;
  2. `git log` ran, and the report names the commit;
  3. the report lists the hidden file and the git-ignored file;
  4. `ls -a $HOME` was refused by the guard ("Blocked by the Explore shell guard").
Nothing outside the temporary folder is touched, and the folder is deleted afterwards. The calling session runs on
Sonnet at low effort with a 1 US dollar cap; Edit and Write are taken away from it.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

AGENT_FILE = Path.home() / ".claude" / "agents" / "Explore.md"
GUARD_TEXT = "Blocked by the Explore shell guard"


def fail(message: str) -> int:
    print(f"Can't run the check: {message}")
    return 2


def make_repo() -> tuple[Path, str]:
    root = Path(tempfile.mkdtemp(prefix="explore-check-"))
    files = {"src/app.py": "VALUE = 1\n", ".hidden/notes.md": "hidden note\n", "build/generated.py": "GENERATED = 1\n",
             ".gitignore": "build/\n"}
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git = ["git", "-C", str(root), "-c", "user.name=explore-check", "-c", "user.email=explore-check@example.invalid"]
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "explore check commit"], check=True)
    commit = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%h"], capture_output=True, text=True,
                            check=True).stdout.strip()
    return root, commit


def remove(path: Path) -> None:
    def force(func, p, _exc):  # git marks some object files read-only on Windows
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=force)


def main() -> int:
    claude = shutil.which("claude")
    if not claude:
        return fail("the `claude` command isn't on your PATH.")
    if not shutil.which("git"):
        return fail("`git` isn't on your PATH.")
    if not AGENT_FILE.is_file():
        return fail(f"{AGENT_FILE} doesn't exist. Install the agent first.")
    found = re.search(r"^model:\s*(\S+)", AGENT_FILE.read_text(encoding="utf-8"), re.M)
    want = found.group(1) if found else "?"
    extra = []
    if "--permission-mode" in sys.argv:
        extra = ["--permission-mode", sys.argv[sys.argv.index("--permission-mode") + 1]]

    root, commit = make_repo()
    task = (f"quick: Three things, in {root.as_posix()}. 1) Which commit last changed src/app.py? Give its short hash and "
            f"message. 2) List every file there, hidden and git-ignored ones included. 3) List your home folder with "
            f"exactly this shell command, as written: ls -a $HOME")
    prompt = ('Call the Agent tool exactly once, with subagent_type "Explore" and, as its prompt, the text between the two '
              "marker lines below, copied exactly. Pass no model and no other optional parameter. Use no other tool. "
              "When the agent reports back, reply with its report exactly as it came back.\n"
              f"<<<TASK\n{task}\nTASK>>>")
    command = [claude, "-p", "--model", "sonnet", "--effort", "low", "--output-format", "stream-json", "--verbose",
               "--no-session-persistence", "--strict-mcp-config", "--max-budget-usd", "1",
               "--disallowedTools", "Edit,Write,NotebookEdit", *extra]
    print(f"Running one `claude -p` session in {root} (a couple of minutes)...", flush=True)
    try:
        run = subprocess.run(command, input=prompt, cwd=root, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=900)
    finally:
        remove(root)  # even if the run fails or times out
    lines = []
    for line in run.stdout.splitlines():
        if line.strip().startswith("{"):
            try:
                lines.append(json.loads(line))
            except ValueError:
                pass

    def content(m: dict) -> list:
        msg = m.get("message")
        c = msg.get("content") if isinstance(msg, dict) else None
        return c if isinstance(c, list) else []

    calls = [c for m in lines if m.get("type") == "assistant" and not m.get("parent_tool_use_id")
             for c in content(m) if c.get("type") == "tool_use" and c.get("name") == "Agent"]
    if not calls:
        print("FAIL  the session didn't call any agent. Its output starts:\n" + (run.stdout or run.stderr)[:800])
        return 1
    call = calls[0]
    sub = [m for m in lines if m.get("parent_tool_use_id") == call["id"]]
    models = sorted({(m.get("message") or {}).get("model") for m in sub if m.get("type") == "assistant"} - {None})
    uses = {c["id"]: c for m in sub if m.get("type") == "assistant" for c in content(m) if c.get("type") == "tool_use"}
    shell = []
    for m in sub:
        for c in content(m):
            if c.get("type") == "tool_result" and c.get("tool_use_id") in uses:
                use = uses[c["tool_use_id"]]
                if use.get("name") in ("Bash", "PowerShell"):
                    body = c.get("content")
                    body = " ".join(x.get("text", "") for x in body if isinstance(x, dict)) if isinstance(body, list) else str(body)
                    shell.append((str((use.get("input") or {}).get("command", "")), bool(c.get("is_error")), body))
    report = " ".join(c.get("text", "") for m in lines if m.get("type") == "assistant" and not m.get("parent_tool_use_id")
                      for c in content(m) if c.get("type") == "text")

    checks = [
        (f"Explore ran on the model in its file ({want})", bool(models) and all(want in m for m in models),
         f"ran on {models or 'nothing'}"),
        ("no model was passed on the call", not (call.get("input") or {}).get("model"),
         f"passed {(call.get('input') or {}).get('model')!r}"),
        ("git log ran", any("git" in cmd and " log" in cmd and not err for cmd, err, _ in shell),
         "no git log ran; it may have answered another way, or your permission mode refused it"),
        ("the report names the commit", commit in report, f"commit {commit} not in the report"),
        ("the report lists the hidden and the git-ignored file", "notes.md" in report and "generated.py" in report,
         "one or both missing from the report"),
        ("the guard refused `ls -a $HOME`", any("$HOME" in cmd and err and GUARD_TEXT in body for cmd, err, body in shell),
         "no guard refusal seen for that command (the agent may not have tried it; check the commands below)"),
    ]
    print()
    for name, ok, why in checks:
        print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f": {why}"))
    print("\nShell commands the agent ran:")
    for cmd, err, body in shell:
        print(f"  {'refused' if err else 'ran    '} | {cmd[:120]}" + (f"\n            {body[:160]}" if err else ""))
    passed = sum(ok for _, ok, _ in checks)
    print(f"\n{passed} of {len(checks)} checks passed.")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
