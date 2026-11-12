"""PreToolUse guard for the Explore agent's shell (version 3, November 2026). docs/GUARD.md has the design, the threat
model, and the holes found and fixed in versions 1 and 2.

Claude Code runs this before every Bash call the helper makes, with the call as JSON on standard input. It lets
through only commands that list files or read git history; anything else is blocked (exit code 2, with the reason
on standard error, which the helper sees). Any error inside the guard blocks too, and the hook is set with
onFailure: "block", so a guard that can't start (no Python, a wrong path) blocks rather than letting the call run.

It is one of two gates. For a command it lets through it says nothing, so the session's own permission check
(auto mode, a prompt, or the permission rules) still decides, as it does for the built-in's shell. Only with
--allow on the hook's command line (used by the test harness, which runs in don't-ask mode; a helper can't set it)
does it answer "allow" and skip that check.

How it reads a command: the way bash does, after banning everything that would make bash do more than run the
words it's given. Banned anywhere, quoted or not: $ (variables and $( ) substitution; only $?, the last exit code,
is allowed), backticks, new lines and other control characters, and a single & (it starts a second command).
Banned outside quotes: > and < (except 2>/dev/null, >/dev/null, &>/dev/null and 2>&1), { }, and ( ) unless escaped
as \\( \\) for find. What's left is words, quotes, backslashes and the joins && || ; |, which this file splits
exactly as bash would, removing quotes and backslashes, so -e"x"ec or -ex\\ec is seen as the -exec it becomes.
Command names are compared as written (LS or FIND is refused).

Allowed: parts joined by && || ; or |, each starting with ls, find, git, cd, pwd, echo or true; after a pipe, also
head, tail, wc, sort or uniq, with plain flags only, and a number only where a flag takes one (head -n 5,
sort -k 2), so they can't be handed a file name.
- find may not use -exec, -execdir, -ok, -okdir, -delete, -fprint, -fprint0, -fprintf, -fls, -files0-from or
  -rm (bfs's delete).
- git: only log, ls-files and rev-parse (with --no-pager and one -C <folder> before them), each with a list of
  allowed options: log takes a count, --oneline, --format=, --pretty=, --date=, --name-only, --name-status,
  --follow, --all, --reverse, --merges, --no-merges, --first-parent, --since=, --until=, --after=, --before=,
  --author=, --grep=, -i, --abbrev-commit, --skip=, --diff-filter=, --max-count=, --no-show-signature and --;
  ls-files takes --, -z, --full-name and --cached; rev-parse takes --show-toplevel, --git-dir,
  --is-inside-work-tree, --abbrev-ref and --short. No %G format codes (they check signatures).
- find and git words may not hold an unquoted wildcard (a planted file named -delete could become an option).
- No word may be a network path (//server/share or \\\\server\\share, also after an =): listing one makes Windows
  contact that server and offer the user's sign-in.
PowerShell is blocked outright: the helper has no PowerShell tool, and this guard only understands bash.

Known limit, the same for the built-in's shell and for running git yourself: any git command trusts the
configuration inside the repository it reads. In a folder that came with a hostile .git folder, even git log can
run a program. The helper only reads folders it is pointed at; this can't be closed from outside git.
"""
from __future__ import annotations  # lets Python 3.7 to 3.9 run it too

import json
import re
import sys

ALLOW = "--allow" in sys.argv[1:]
STARTERS = {"ls", "find", "git", "cd", "pwd", "echo", "true"}
# Filters may only follow a pipe. Their flags, and the flags that take the next word as a value (with its shape).
FILTER_FLAGS = {
    "head": re.compile(r"-[0-9]+|-[nc][0-9]+|-q"),
    "tail": re.compile(r"-[0-9]+|-[nc]\+?[0-9]+|-q"),
    "wc": re.compile(r"-[lcwm]+"),
    "sort": re.compile(r"-[bfhinruV]+|-k[0-9][0-9.,bfhinrV]*"),
    "uniq": re.compile(r"-[cdiu]+"),
}
FILTER_VALUES = {
    "head": ({"-n", "-c"}, re.compile(r"[0-9]+")),
    "tail": ({"-n", "-c"}, re.compile(r"\+?[0-9]+")),
    "sort": ({"-k"}, re.compile(r"[0-9][0-9.,bfhinrV]*")),
}
GIT_OK = {"log", "ls-files", "rev-parse"}
LOG_FLAGS = {"--oneline", "--name-only", "--name-status", "--follow", "--all", "--reverse", "--merges", "--no-merges",
             "--first-parent", "-i", "--abbrev-commit", "--no-show-signature"}
LOG_VALUE_PREFIXES = ("--format=", "--pretty=", "--date=", "--since=", "--until=", "--after=", "--before=",
                      "--author=", "--grep=", "--skip=", "--diff-filter=", "--max-count=")
LS_FILES_FLAGS = {"-z", "--full-name", "--cached"}
REV_PARSE_FLAGS = {"--show-toplevel", "--git-dir", "--is-inside-work-tree", "--abbrev-ref", "--short"}
FIND_BAD = {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls", "-files0-from",
            "-rm"}  # -rm: bfs, which runs as find in Claude Code's shell on macOS and Linux, deletes with it
HARMLESS = re.compile(r"(?:2>&1|&>\s?/dev/null|[12]?>\s?/dev/null)(?=$|[\s;|&])")
CONTROL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")
SINGLE_AMP = re.compile(r"(?<!&)&(?!&)")
NET_PATH = re.compile(r"(?:^|=)(?://|\\\\)")
ONLY = "this shell is only for listing files (ls, find) and reading git history (git log)"


def tokenize(text: str):
    """Split into parts as bash would: a list of (the join before the part, [(word, has an unquoted wildcard)]),
    each word with its quotes and backslashes removed. Returns a reason string for anything it won't model."""
    parts, words, word, wild, join = [], [], None, False, ""
    i, n = 0, len(text)
    while i < n:
        ch, two = text[i], text[i:i + 2]
        if ch in " \t" or two in ("&&", "||") or ch in ";|":
            if word is not None:
                words.append(("".join(word), wild))
                word, wild = None, False
            if ch in " \t":
                i += 1
                continue
            if words:
                parts.append((join, words))
            words = []
            join = two if two in ("&&", "||") else ch
            i += len(join)
            continue
        if word is None:
            word = []
        if ch == "\\":
            if i + 1 >= n:
                return "a trailing backslash isn't allowed"
            word.append(text[i + 1])
            i += 2
        elif ch == "'":
            j = text.find("'", i + 1)
            if j < 0:
                return "an unclosed quote isn't allowed"
            word.append(text[i + 1:j])
            i = j + 1
        elif ch == '"':
            j, buf = i + 1, []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n and text[j + 1] in '"\\':
                    buf.append(text[j + 1])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            if j >= n:
                return "an unclosed quote isn't allowed"
            word.append("".join(buf))
            i = j + 1
        elif ch in "<>{}()":
            if ch in "()":
                return "'(' and ')' aren't allowed, except escaped as \\( \\) for find"
            return f"'{ch}' isn't allowed: {ONLY}"
        else:
            if ch in "*?[":
                wild = True
            word.append(ch)
            i += 1
    if word is not None:
        words.append(("".join(word), wild))
    if words:
        parts.append((join, words))
    return parts


def filter_problem(name: str, words: list) -> str | None:
    flags = FILTER_FLAGS[name]
    takes, value = FILTER_VALUES.get(name, (set(), None))
    i = 1
    while i < len(words):
        w, wild = words[i]
        if wild:
            return f"'{name}' may only filter piped output here (no wildcards)"
        if w in takes:
            if i + 1 < len(words) and not words[i + 1][1] and value.fullmatch(words[i + 1][0]):
                i += 2
                continue
            return f"'{name} {w}' needs a number after it"
        if not flags.fullmatch(w):
            return f"'{name}' may only filter piped output here, with simple flags (not {w})"
        i += 1
    return None


def git_problem(w: list[str]) -> str | None:
    rest = w[1:]
    while rest and rest[0] == "--no-pager":
        rest = rest[1:]
    if rest and rest[0] == "-C":
        rest = rest[2:]
    while rest and rest[0] == "--no-pager":
        rest = rest[1:]
    if not rest or rest[0] not in GIT_OK:
        return "git may only read history here: git log (or ls-files, rev-parse)"
    sub, args = rest[0], rest[1:]
    paths_only, i = False, 0
    while i < len(args):
        x = args[i]
        if "%G" in x:
            return "git's %G format codes (signatures) aren't allowed here"
        if paths_only or not x.startswith("-"):
            i += 1
            continue
        if x == "--" and sub in ("log", "ls-files"):
            paths_only = True
        elif sub == "log":
            if x == "-n" and i + 1 < len(args) and args[i + 1].isdigit():
                i += 1
            elif not (x in LOG_FLAGS or re.fullmatch(r"-[0-9]+|-n[0-9]+", x) or x.startswith(LOG_VALUE_PREFIXES)):
                return f"git log's {x.split('=', 1)[0]} option isn't allowed here"
        elif sub == "ls-files":
            if x not in LS_FILES_FLAGS:
                return f"git ls-files' {x} option isn't allowed here (find lists ignored and untracked files)"
        elif not (x in REV_PARSE_FLAGS or re.fullmatch(r"--short=[0-9]+", x)):
            return f"git rev-parse's {x} option isn't allowed here"
        i += 1
    return None


def check(command: str) -> str | None:
    """None if the command is allowed, else the reason it isn't."""
    if CONTROL.search(command):
        return "new lines and other control characters aren't allowed: put the command on one line, joined with &&"
    # $? (the last command's exit code, a number) is the one expansion allowed: helpers print it after git log.
    text = HARMLESS.sub(" ", command).replace("$?", "0")
    if "$" in text:
        return "'$' isn't allowed (no variables or $( ) substitution), even inside quotes"
    if "`" in text:
        return "backticks aren't allowed, even inside quotes"
    if SINGLE_AMP.search(text):
        return "a single '&' isn't allowed (it starts a second command)"
    parts = tokenize(text)
    if isinstance(parts, str):
        return parts
    if not parts:
        return "an empty command isn't allowed"
    for join, words in parts:
        if any(NET_PATH.search(w) for w, _ in words):
            return "network paths (//server/share) aren't allowed"
        first, first_wild = words[0]
        if join == "|" and first in FILTER_FLAGS:
            problem = filter_problem(first, words)
            if problem:
                return problem
            continue
        if first_wild or first not in STARTERS:
            return f"'{first}' isn't allowed: {ONLY}"
        if first in ("find", "git") and any(wild for _, wild in words[1:]):
            return f"{first} wildcards must be in quotes here, for example -name '*.py'"
        if first == "find":
            bad = [w for w, _ in words if w.lower() in FIND_BAD]
            if bad:
                return f"find may only list: {bad[0]} isn't allowed"
        if first == "git":
            problem = git_problem([w for w, _ in words])
            if problem:
                return problem
    return None


def main() -> int:
    try:
        call = json.load(sys.stdin)
        tool = call.get("tool_name")
        if tool == "PowerShell":
            reason = "PowerShell isn't available to this helper; use the Bash tool with ls, find or git log"
        elif tool != "Bash":
            return 0
        else:
            reason = check(str((call.get("tool_input") or {}).get("command", "")))
        if reason:
            print(f"Blocked by the Explore shell guard: {reason}. Read file contents with Read, carry on with Glob, "
                  "Grep and Read, and say in your report what you couldn't check.", file=sys.stderr)
            return 2
        if ALLOW:  # test harness only: skip the session's own permission check
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                                     "permissionDecisionReason": "listing or git history only"}}))
        return 0
    except BaseException as exc:  # fail closed: anything unexpected blocks the call
        try:
            print(f"The Explore shell guard hit an error ({type(exc).__name__}), so the call was blocked.",
                  file=sys.stderr)
        except BaseException:
            pass
        return 2


if __name__ == "__main__":
    sys.exit(main())
