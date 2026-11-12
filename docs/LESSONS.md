# What we learnt replacing Claude Code's Explore subagent

Notes from testing a cheaper Explore agent against the built-in (November 2026, Claude Code 2.1.321, Windows). Useful if you're doing something similar, whether or not you use this agent.

## About Claude Code

- **The built-in Explore runs on your session's model,** not a small one. Under a Fable session on a subscription it runs on Opus. Searches are frequent, so this is a real cost.
- **A user or project agent named `Explore` replaces the built-in** and keeps its own `model:` line. The docs recommend this.
  - A model named on the call still beats the file. If your CLAUDE.md says "always name a model for subagents", add an exception for Explore.
  - `CLAUDE_CODE_SUBAGENT_MODEL` alone doesn't move the built-in Explore. Adding `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` moves every subagent and ignores per-call models, which is usually too blunt.
- **On macOS, Linux and WSL, a subagent gets Grep and Glob only if it has no shell** (Claude Code's tools reference). There, Claude Code searches through the shell instead, with its own `find` (`bfs`) and `grep` (`ugrep`). An agent that needs both search tools and a shell, like this one, is Windows-only for now.
- **Grep and Glob see different things.** Grep skips git-ignored files by design. Glob includes git-ignored and hidden files, but stops at 100 results and can time out on a huge tree. Either way, a big git-ignored folder can go unseen: a shell listing is what finds it.
- **Hook behaviour worth knowing:**
  - `onFailure: "block"` (2.1.295 and later) makes a hook that can't start, crashes or times out block the action. Without it, the action goes ahead.
  - A hook answering `permissionDecision: "allow"` skips the user's prompt or auto mode. Deny and ask rules still apply. A guard that answers "allow" is therefore the only gate for what it passes.
  - Hooks in a user-level agent's frontmatter run without a trust prompt.
- **Running sessions do pick up a new agent file, but not straight away.** In our test, a session open during the install still used the built-in two and a half minutes later, and the new agent an hour or two later. Restart to be sure.
- **Main sessions often search by themselves.** In our trials, an Opus session answered two ordinary questions without calling any subagent. Swapping Explore saves only on the searches that get delegated.

## About shell guards

- **A shell guard that passes your tests can still be wide open.** Ours passed its own 25 tests and over 500 real runs, then an adversarial check found 11 ways round it, and a separate review of the fix, by a stronger AI model, found more. Test a guard as an attacker would, not just with the commands you expect.
- **What made it hold up:**
  - Read the command the way bash does (quotes, backslashes, wildcards, joins), not by splitting on spaces.
  - Ban what makes bash do more than run words: `$`, backticks, new lines, a lone `&`, redirects, braces and brackets.
  - List allowed options, not banned ones. A ban list misses abbreviations and the next option nobody thought of.
  - Refuse network paths. On Windows, listing `//server/share` makes the machine contact that server.
  - Fail closed: catch every error, and declare the hook with `onFailure: "block"`.
  - Never answer "allow". Let the user's permission check stay a second gate.
- **Replay real commands after every change.** Record every shell command your agent runs in testing, and check each new guard version against all of them. That's how you know a fix didn't break what the agent needs.

## About testing a subagent

- **Test it the way it's really used.** A `claude -p` caller that calls the agent through the Agent tool gives the agent's real model, tools and usage from the stream. Running the agent as the main session isn't quite the same.
- **Test against today's way of doing it,** here the built-in, on the same tasks and on the same day.
- **Grade blind, and show the grader the cited lines.** A grader that can see what each `file:line` really holds catches confident wrong claims.
- **Count ungraded answers before ranking anything.** Our grader stopped partway through, 43 answers went ungraded, and the comparison counted them as failures. That briefly made the cheapest setup look worse. Make your comparison refuse to give a verdict while anything is ungraded.
- **Small samples mislead.** With one to three runs per task, small models first looked better than Opus, then worse. Five rounds evened it out.
- **Don't score your agent's own extra rules as task passes.** Ours was told to report planted instructions. Counting that against the built-in, which was never told to, was unfair.
- **Plant traps:** a note telling AI assistants to give a wrong answer, a note asking them to run a script (with a marker file to catch it), a fake secret in a git-ignored file, look-alike copies, a folder that doesn't exist.
- **Check your test plumbing.**
  - Test files copied outside the working folder were unreadable in don't-ask mode, so every arm failed those tasks equally until we passed `--add-dir`.
  - Once our own `Explore` was installed, reaching the built-in for comparison needed `--setting-sources project,local`, which leaves out user-level agents. Check this still holds on your version.
- **Answer keys based on live projects go stale.** Re-check them before every comparison.
- **"List everything" questions are the weak spot on every model,** the built-in included. Totals in such answers are often wrong: read the list, not the count.
