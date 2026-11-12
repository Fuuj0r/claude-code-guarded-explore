<p align="center">
  <img src=".github/img/logo.svg" alt="Guarded Explore logo" width="150" />
</p>

# Guarded Explore

A drop-in replacement for Claude Code's built-in **Explore** subagent. Tested head to head against the built-in, it gave answers as good, at about **a seventieth of the usage per search**, with a safer shell.

*Windows only for now · Claude Code 2.1.295 or later · MIT licence · not affiliated with or endorsed by Anthropic*

[Latest release](https://github.com/Fuuj0r/claude-code-guarded-explore/releases/latest) · [How it was tested](docs/RESULTS.md) · [How the guard works](docs/GUARD.md) · [What we learnt](docs/LESSONS.md) · [Report a way round the guard](SECURITY.md)

## <img src=".github/img/lightbulb.svg" width="24" height="24" alt=""> The problem it solves

When Claude Code needs to search a codebase, it usually hands the job to its built-in Explore subagent. That subagent runs on your main session's model. If you work on Opus, every search runs on Opus; under a Fable session on a subscription, Explore runs on Opus too. Searches happen a lot, so this adds up. Several GitHub issues asked for a setting to change it, and they were closed without one.

Claude Code's documentation gives the fix: create your own agent named `Explore`, which replaces the built-in and keeps its own `model:` line. The version usually shared does exactly that with only Read, Grep and Glob. In our tests, that no-shell version:
* missed files inside **git-ignored folders**: Grep skips them by design, and in a large folder Glob's 100-result limit cut them off;
* answered **git history** questions, such as "which commit last changed this file?", less than half the time (4 of 9).

**The built-in does both, with its shell. So Guarded Explore:**
* **runs on Haiku** instead of your main session's model;
* **keeps a shell**, but a guard lets that shell only list files and read git history.

> [!IMPORTANT]
> **Windows only for now.** It's tested on Windows 11. Don't install it on macOS, Linux or WSL yet: there, Claude Code gives a subagent its Grep and Glob tools only if it has no shell, so this agent couldn't search file contents. The installer stops on those systems. See [Limits](#-limits).

## <img src=".github/img/chart-column.svg" width="24" height="24" alt=""> At a glance

| | Built-in Explore | Guarded Explore (this) |
| :--- | :---: | :---: |
| Model it runs on | Your session's model (often Opus) | Haiku |
| **Usage per search** (API rates) | about 29 US cents | **about 0.4 US cents** |
| Searches fully correct (of 85) | 83 | 84 |
| Serious mistakes (wrong fact stated as fact) | 2 | 1 |
| Median time per search | 16 s | 13 s |
| Finds files in git-ignored folders | Yes | Yes |
| Answers git-history questions | Yes | Yes |
| What its shell can do | Anything your permission mode allows | Only list files and read git history |

From 614 real subagent calls on 17 search tasks, graded blind; 493 of them count towards this table, because three tasks were re-run after a fault in the test set-up. The quality differences are within chance: answers as good, for far less. The usage row is from an earlier run of 14 of these tasks, where exact token counts were available; the 614 calls showed a ratio at least as wide. [How it was tested](docs/RESULTS.md).

## <img src=".github/img/terminal.svg" width="24" height="24" alt=""> Install (about a minute)

You need Windows, Claude Code 2.1.295 or later, Git Bash (Claude Code uses it for shell commands on Windows) and Python 3.9 or later. To check Python, run this in a terminal:

```shell
python --version
```

1. **Download it.** Open the [latest release](https://github.com/Fuuj0r/claude-code-guarded-explore/releases/latest), and under **Assets** download the file ending **`-windows.zip`**.
2. **Unzip it** (right-click it and choose Extract All), **then double-click `install.cmd`** in the unzipped folder. It shows what it will do and asks first. (Or run `python install.py` in that folder.)
3. **Restart Claude Code,** or start a new session.

That's it. The installer copies two files into your `~/.claude` folder and tests the guard it installed.
* **If you already have an Explore agent,** it keeps a backup.
* **If you re-install over an edited copy** (say you switched it to Sonnet), it keeps your model and effort choices.
* **To remove it:** double-click `uninstall.cmd`, or run `python install.py --uninstall`. That puts back your old Explore agent, if you had one.

#### Other ways to install

<details>
<summary><b>A single file</b> (<code>guarded-explore-setup-&lt;version&gt;.py</code>)</summary>

The release also has **`guarded-explore-setup-<version>.py`**, a one-file installer with everything built in. Run it, or double-click it:

```shell
python guarded-explore-setup-<version>.py
```

If Windows asks which app to open it with, choose Python; if it opens in an editor instead, use the `python` command. To remove it later, run the same file with `--uninstall`.
</details>

<details>
<summary><b>Ask Claude Code to do it</b></summary>

> Download the latest -windows.zip from https://github.com/Fuuj0r/claude-code-guarded-explore/releases, unzip it, run `python install.py --check` in its folder and show me the output. If I say yes, run `python install.py --yes`.
</details>

<details>
<summary><b>The "Source code" downloads</b></summary>

The "Source code" downloads GitHub adds to every release are the whole repository, for developers. You don't need them to install.
</details>

> [!TIP]
> **One optional line for your CLAUDE.md.** If your CLAUDE.md tells Claude to name a model for every subagent, add this, because a model named on the call overrides the agent's own:
>
> *Explore has its own model and effort in its file, so pass no model on an Explore call. For a search a costly decision rests on, open the lines it cites yourself, and check a "list everything" answer with the shell.*

#### Prove it works on your machine

```shell
# Should end "mismatches: 0"
python tests/test_shell_guard.py --installed

# Should end "6 of 6 checks passed" (one short Claude session in a throwaway folder)
python tools/check_install.py
```

## <img src=".github/img/badge-check.svg" width="24" height="24" alt=""> Why use this

### Instead of the built-in Explore: answers as good, for about a seventieth of the price

<table width="100%">
  <tr>
    <td width="33%" valign="top">
      <h4>🎯 Same quality</h4>
      <p>Over 85 graded searches each, it fully passed 84 to the built-in's 83, with fewer serious mistakes (1 against 2). That difference is within chance: call it a draw.</p>
    </td>
    <td width="33%" valign="top">
      <h4>💰 About 70 times cheaper</h4>
      <p>The built-in runs on your main session's model; this runs on Haiku. Per search, about 0.4 US cents against about 29 at API rates, with the built-in on Opus. On a subscription, that's usage you keep for real work.</p>
    </td>
    <td width="33%" valign="top">
      <h4>⚡ No slower</h4>
      <p>The median search took 13 seconds against 16.</p>
    </td>
  </tr>
  <tr>
    <td width="33%" valign="top">
      <h4>🔍 Nothing lost</h4>
      <p>It still finds files in hidden and git-ignored folders, and reads git history: the two things the built-in's shell is for. It matched the built-in on both in every round.</p>
    </td>
    <td width="33%" valign="top">
      <h4>🛡️ A safer shell</h4>
      <p>The built-in's shell can do anything your permission mode allows. This one can only list files and read git history, and your permission mode still applies on top. In testing, the built-in tried to read a <code>.env</code> file through its shell (redacting the values as it went); this guard refuses that.</p>
    </td>
    <td width="33%" valign="top">
      <h4>⚓ Steady</h4>
      <p>Its model doesn't change when your session's does. Under a Fable session, the built-in Explore runs on Opus; this stays on Haiku.</p>
    </td>
  </tr>
</table>

**Tested properly, not on a handful of tries:**
* 614 real subagent calls: 17 search tasks, 5 rounds, the built-in and three setups of this agent, plus a no-shell version for comparison. 493 of them count towards the tables, because three tasks were re-run after a fault in the test set-up.
* every answer graded blind, by a model shown the exact lines the answer cited;
* a second, stronger model re-checked every failure and a quarter of the passes;
* disputes were settled against the source files by a fixed rule;
* the tasks included traps: notes planted in files telling AI assistants to give a wrong answer or run a script, a fake secret in a git-ignored `.env`, look-alike copies of files, and a folder that doesn't exist.

The method is in [docs/RESULTS.md](docs/RESULTS.md).

### Instead of other Explore replacements

As far as we could find (November 2026), the replacements people share fall into three groups.

* **No shell.** Read, Grep and Glob on Haiku: the version in blog posts, built on a one-line suggestion in Claude Code's docs. It's cheap, but in our tests, this agent with its shell removed (the same tools), across three model setups:
  * found 0 to 3 of 6 scripts in a git-ignored folder, where the built-in and this agent found all 6;
  * named the commit behind a file in 4 of 9 runs, where both found it every time.

  It scores well only because an honest "I couldn't check" counts as a fair answer.
* **A read-only shell guard applied to every subagent.** Useful, but the ones we found allow commands such as `cat` and `sed`, so a subagent can still read a `.env` file through the shell.
* **A search agent on Haiku under another name, with an ordinary shell.** Cheap, but its shell is as open as the built-in's, and Claude only uses it when it picks that agent over the built-in.

This agent combines what those miss:
* **a shell** for git-ignored folders and git history;
* **a guard that refuses reading file contents through the shell,** `$` variables, command substitution, network paths and anything it can't parse. It understands quoting the way bash does, and it fails closed if it can't run.
* **The guard never approves anything itself,** so your permission mode stays in charge.
* **It has been attacked:**
  * the first version passed its own tests and over 500 test runs, then an adversarial check found 11 ways round it;
  * a separate review by a stronger AI model found more in the second;
  * all are fixed, and all are in the 110 tests.

  The history is in [docs/GUARD.md](docs/GUARD.md).
* **Evidence:** the published comparisons we found tested one easy lookup a handful of times, or three inventory questions, 36 runs in all. None tested git-ignored folders, git history, planted instructions or secrets. This one did.

## <img src=".github/img/flask-conical.svg" width="24" height="24" alt=""> Results in more detail

Tested on Windows 11 with Claude Code 2.1.321, in November 2026, on 17 search tasks over 5 rounds: 614 subagent calls, graded blind, of which 493 count towards the tables (three tasks were re-run after a fault in the test set-up). Details and caveats are in [docs/RESULTS.md](docs/RESULTS.md).

| | Fully passed (of 85) | Serious mistakes* | Usage per search (API rates) |
| :--- | :---: | :---: | :---: |
| Built-in Explore (Opus, high effort) | 83 | 2 | about 29 US cents |
| **This agent, Haiku, medium effort** | **84** | **1** | **about 0.4 US cents** |
| This agent, Sonnet, medium effort | 85 | 0 | about 4.2 US cents |

\* A wrong fact stated as fact, such as a wrong file, function or line.

| What the shell is for | Built-in | This agent (Haiku) | Same agent, no shell |
| :--- | :---: | :---: | :---: |
| Found the 6 scripts in a git-ignored folder (per round) | 6, 6, 6, 6, 6 | 6, 6, 6, 6, 6 | 0 to 3 |
| Named the commit that last changed a file | 5 of 5 | 5 of 5 | 4 of 9 |

The quality differences between the top three are within chance. The point is the saving, and that the saving doesn't cost you anything the built-in does.

## <img src=".github/img/package.svg" width="24" height="24" alt=""> What's in here

| File | What it is |
| :--- | :--- |
| `install.cmd`, `uninstall.cmd` | Double-click to install or remove. |
| `install.py` | What they run. It installs and uninstalls (`--uninstall`); `--check` shows what it would do. |
| `agents/Explore.md` | The agent (Haiku, medium effort; Read, Grep, Glob and a guarded Bash). |
| `hooks/explore_shell_guard.py` | The guard, a PreToolUse hook that runs before every shell command the agent tries. |
| `tests/test_shell_guard.py` | 110 tests, including every way round the guard found so far. |
| `tests/test_installer.py` | 19 checks of the installer and of both release downloads, in throwaway folders (never your real one). Passes on Python 3.9 and 3.15. |
| `tools/build_release.py` | Builds the two release downloads (for maintainers). |
| `tools/check_install.py` | An end-to-end check on your own machine (one short `claude -p` session). |
| `docs/` | [RESULTS.md](docs/RESULTS.md) (how it was tested), [GUARD.md](docs/GUARD.md) (how the guard works, and its limits) and [LESSONS.md](docs/LESSONS.md) (what we learnt). |

## <img src=".github/img/wrench.svg" width="24" height="24" alt=""> Manual install (instead of install.py)

1. Copy `hooks/explore_shell_guard.py` to `~/.claude/hooks/` (make the folder if it isn't there).
2. Copy `agents/Explore.md` to `~/.claude/agents/`. If your system only has `python3`, change `python` to `python3` in its hook command.
3. Restart Claude Code. A running session should pick up the new file, but in our test it took a while.

**Undo:** delete those two files (and the CLAUDE.md line, if you added it), then restart.

> [!TIP]
> **To use Sonnet instead,** change `model: haiku` to `model: sonnet` in the installed agent file. In our tests it had no serious mistakes, at about a seventh of the built-in's usage.

## <img src=".github/img/shield-check.svg" width="24" height="24" alt=""> How the guard works

The agent's shell may run only `ls`, `find` (without `-exec`, `-delete` and the like), `git log`, `git ls-files`, `git rev-parse`, `cd`, `pwd`, `echo` and `true`. After a pipe it may also use `head`, `tail`, `wc`, `sort` and `uniq`, with plain options only. Everything else is refused, with a message telling the agent to carry on with its other tools:
* running programs;
* reading file contents through the shell;
* writing, deleting, network paths;
* `$` variables and command substitution.

Two things make it safer than a simple allow-list:
* **It never approves a command itself.** Anything it lets through still goes through your session's own permission check, as the built-in's shell does. So it's a second gate, not a replacement for your permission mode.
* **It fails closed.** The hook uses `onFailure: block`, so if the guard can't run at all (Python missing, a wrong path), the agent's shell is refused rather than left open.

The design, the threat model, the known limits and the holes found in earlier versions are in [docs/GUARD.md](docs/GUARD.md).

## <img src=".github/img/triangle-alert.svg" width="24" height="24" alt=""> Limits

* **Tested narrowly:** one Windows PC, one person's projects as test cases, one Claude Code version.
* **Windows only.** On macOS, Linux and WSL it won't work as shipped. There, Claude Code gives a subagent the Grep and Glob tools only if it has no shell, so this agent would be left unable to search file contents. Its `find` is also a different program there. The installer stops on those systems.
* **Tested and reviewed by AI models,** not audited by a security professional.
* **A project's own `.claude/agents/Explore.md` wins over this one** inside that project.
* **Not smarter than the built-in;** level with it, for much less.
* **"List everything" answers can miss files,** on every model, the built-in included. In one later run, this agent skipped a folder it took for generated code. Check with the shell when completeness matters.
* **Your main session may not use it much:** it often searches by itself without calling Explore, and the saving only applies when it does.
* **The guard is a second gate, not a sandbox.** One known limit: git trusts the configuration inside the repository it reads, so a folder that arrives with a hostile `.git` folder could make even `git log` run a program. The built-in's shell, and git run by hand, have the same exposure.
* **While it's installed, you can't call the built-in Explore,** because the name is taken.
* **Claude Code changes quickly.** Re-run the tests and the check after updates.

## <img src=".github/img/file-text.svg" width="24" height="24" alt=""> Licence

MIT (see [LICENSE](LICENSE)). Not affiliated with or endorsed by Anthropic. Use at your own risk, and read [docs/GUARD.md](docs/GUARD.md) before relying on the guard.

Section icons are from [Lucide](https://lucide.dev) (ISC licence).
