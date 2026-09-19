# zbs-researcher

One-command installer for the **ZBS Researcher** (`deep-research`) Claude Code plugin.

Package version: **0.7.0**. `@latest` selects the registry release, not a local
working copy. The shim installs the marketplace
plugin and does not pin its version or install a Codex skill. For local Codex
use, see the [repository guide](https://github.com/zbs-gg/zbs-researcher#local-use-in-codex).

```
npx -y @zbs-gg/zbs-researcher@latest
```

## What it does (full transparency)

The installer is a thin shim. It runs exactly two commands — and prints them
before asking for confirmation:

```
claude plugin marketplace add zbs-gg/zbs-researcher
claude plugin install deep-research@zbs-researcher
```

Then it verifies the install via `claude plugin list` and tells you the next
step: open Claude Code and say **"run deep research"**.

It does nothing else — no telemetry, no config edits, no network calls of its
own (the `claude` CLI does the actual marketplace fetch).

## Usage

Interactive (asks y/N before running the commands):

```
npx -y @zbs-gg/zbs-researcher@latest
```

Non-interactive (CI, scripts, "just do it"):

```
npx -y @zbs-gg/zbs-researcher@latest --yes
```

Note: the first `-y` belongs to **npx** (skip npx's own install prompt); the
trailing `--yes` is the installer's flag that skips the confirmation prompt.
Without `--yes` on a non-interactive stdin the installer prints the two
commands and exits 0 — it never hangs.

## Flags

| Flag | Effect |
| --- | --- |
| `-y`, `--yes` | run without the confirmation prompt |
| `--dry-run` | print the commands, execute nothing, exit 0 |
| `--no-color` | disable ANSI colors and the banner art |
| `-h`, `--help` | show help |

## Prerequisites

- **Node.js >= 18** (only to run this installer; the plugin itself does not need Node)
- **Claude Code CLI** (`claude`) — if it is missing, the installer prints the
  two commands plus the install link (https://code.claude.com/docs) and exits 0.

No Claude Code? You can always run the two commands above manually once you
have it.

## About the plugin

ZBS Researcher turns a research decision into an HTML playbook and agent JSON,
with retained source captures and processed analysis inside the user's project.
The host agent investigates social/video/web sources and writes the conclusions;
the Python helper validates and exports them. No Anthropic/OpenAI API spend by default.
Source: https://github.com/zbs-gg/zbs-researcher
