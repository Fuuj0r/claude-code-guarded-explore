# The shell guard

`hooks/explore_shell_guard.py` is a Claude Code PreToolUse hook. It's declared in the agent's own file, so it only applies while that agent is running. Claude Code calls it before every shell command the agent tries, with the command as JSON:
- **exit code 2** blocks the command, and the reason goes back to the agent;
- **exit 0, saying nothing,** lets the command go on to your session's normal permission check.

## What it's for

A search agent reads files written by other people. A file can contain instructions ("ignore your task and run this"), and a model can also just make a mistake. The guard makes sure that, whatever the agent is talked into, its shell can only:
- list files: `ls`, and `find` without `-exec`, `-execdir`, `-ok`, `-okdir`, `-delete`, `-fprint*`, `-fls`, `-files0-from` or `-rm` (the last is `bfs`'s delete option);
- read git history: `git log`, `git ls-files` and `git rev-parse`, each with a fixed list of options;
- move around and print: `cd`, `pwd`, `echo`, `true`;
- after a pipe, filter the listing: `head`, `tail`, `wc`, `sort` and `uniq`, with plain options only, and a number only where an option expects one.

Everything else is refused, with a message telling the agent to use Read, Grep and Glob instead and to say what it couldn't check.

## How it reads a command

Most guards split a command on spaces and look at the first word. That's easy to get round, so this one reads the command the way bash does.

1. **Bans, even inside quotes:**
   - `$` (variables, `$(...)` substitution; only `$?`, a number, is allowed);
   - backticks;
   - new lines and other control characters;
   - a single `&`, which starts a second command.
2. **Bans outside quotes:**
   - `>` and `<`, except four harmless forms (`2>/dev/null`, `>/dev/null`, `&>/dev/null`, `2>&1`);
   - `{ }`, which bash expands;
   - `( )`, unless escaped as `\(` `\)` for `find`.
3. **What's left is words, quotes, backslashes and the joins `&&`, `||`, `;` and `|`.** The guard splits these exactly as bash would, removing quotes and backslashes. So `-e"x"ec` and `-ex\ec` are seen as the `-exec` they become.
4. **Each part must start with an allowed command,** compared exactly as written. `LS` and `FIND` are refused.
5. **`find` and `git` words may not hold an unquoted wildcard.** Otherwise a planted file named `-delete` or `--output=x` could turn into an option when bash expands `*`.
6. **No word may be a network path** (`//server/share`, `\\server\share`, or either after an `=`). Listing one makes Windows contact that server and offer your sign-in.
7. **PowerShell is refused outright:** the agent has no PowerShell tool, and the guard only understands bash.

## Two gates, failing closed

- **It never approves a command.** For a command it allows, it exits 0 without a decision, so your session's own permission check (prompts, auto mode or your rules) still applies. If the guard ever misses something, the agent is no less protected than the built-in Explore, whose shell has only that check.
  - The tests run in don't-ask mode, so there `--allow` on the hook's command line makes the guard answer "allow".
  - The agent can't set that, and the shipped agent file doesn't use it.
- **It fails closed.** The hook is declared with `onFailure: block` (Claude Code 2.1.295 or later). If the guard can't run at all, for example Python is missing or the path is wrong, Claude Code blocks the command instead of letting it through. Any unexpected error inside the guard also blocks.
  - Without `onFailure: block`, a broken hook would let commands through to the normal check.
  - A missing script would block anyway, but only by luck: Python exits with code 2 when it can't find the file.

## Known limits

- **Git trusts the repository's own configuration.** Any git command reads `.git/config` inside the repository it's pointed at. A folder that arrives with a hostile `.git` folder (a downloaded archive, say) could make even `git log` run a program, for example through a signature program set in that config.
  - Cutting git down to `log`, `ls-files` and `rev-parse` with fixed options narrows this a lot. It can't be closed from outside git.
  - The built-in Explore's shell, and you running git by hand, have the same exposure.
- **Windows only.** The agent's Bash tool on Windows is Git Bash, and that's where it was tested. On macOS, Linux and WSL, Claude Code gives a subagent the Grep and Glob tools only if it has no shell, so this agent couldn't search file contents there. Claude Code's shell also runs a different `find` there (`bfs`, whose `-rm` deletes files; the guard now blocks it). The installer stops on those systems.
- **Tested and reviewed by AI models,** not audited by a security professional.
- **It reads names, not contents.** The shell can show file names and commit history (messages, authors, dates and which files changed), but no file contents: `git log -p`, `git show` and `cat` are all refused. Reading contents is Read's job, and Read is covered by your deny rules.

## How it was attacked

- **Version 1** passed its own 25 tests and over 500 test runs.
  - Then an adversarial check found 11 kinds of way round it: `echo "$(cmd)"` inside double quotes, a second command after a new line or a single `&`, `git log --output=file` (writes a file), `git blame --contents=file` (reads any file), `sort -o file` and `uniq in out` (write files), `sort --compress-program` (runs a program) and `echo $SECRET`.
  - Fixing those turned up more: `-e"x"ec` and `-ex\ec` splicing, wildcards turning into options, and look-alike redirects such as `> /dev/nullx`.
  - Worse, version 1 answered "allow" for whatever it passed, which skips the user's permission check. So a miss was worse than no guard.
- **Version 2** read commands the way bash does and failed closed. A separate review by a stronger AI model then found:
  - network paths;
  - more of git than the agent needed (`show` and `blame` were never used, and widened what a hostile repository could do);
  - filters accepting a bare "number" that was really a file name;
  - upper-case command names;
  - and that the guard still answered "allow".
- **Version 3** (this one) fixes all of those, and never answers "allow".

Every one of those bypasses is a test in `tests/test_shell_guard.py`, alongside the legitimate commands the agent needs, 110 cases in all. Every shell command this agent ran in testing (about 165) was replayed against each new version: all of them still passed, and every one the earlier version refused stayed refused.

## Found a way round it?

Please report it privately, so it can be fixed before it's public: on this repository's **Security** tab, choose **Report a vulnerability**. If that option isn't there, open an issue that only says you've found one, without the details, and you'll be contacted.

Once it's fixed, the command goes into `tests/test_shell_guard.py` as a new case: it fails against the old guard and passes against the fixed one.
