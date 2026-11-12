# Security policy

Guarded Explore's guard should let the agent's shell do only two things: list files and read git history. A command that gets past it and does anything else, such as reading a file's contents, running a program, writing or deleting a file, or reaching a network path, is a security bug.

## Supported versions

Fixes go into the latest release only.

| Version | Supported |
| ------- | --------- |
| 1.0.x   | Yes       |

## Reporting a vulnerability

Please report it privately rather than in a public issue, so it can be fixed first:

1. Open this repository's **Security and quality** tab (**Security** on older screens).
2. Click **Report a vulnerability** and fill in the form.

Please include:
- the exact command that got through, or the steps to reproduce it;
- what it managed to do;
- your Claude Code and Windows versions, if you know them.

If you can't use private reporting, open an issue that says only that you've found a security problem, without the details, and you'll be contacted.

## What happens next

This is a small personal project, so a reply may take a few days. A confirmed report gets a test case and a fix in a new release. Please test only on your own machine and your own projects.
