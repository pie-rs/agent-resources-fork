---
title: "CLI Reference — All agr and agrx Commands, Flags, and Options"
description: Complete CLI reference for agr and agrx — all commands, flags, and handle formats for managing skills across Claude Code, Cursor, Codex, OpenCode, Copilot, and Antigravity.
keywords:
  - agr CLI reference
  - agr commands
  - agr add command
  - agr remove command
  - agr sync command
  - agr config command
  - agrx command
  - agr handle format
  - agr.toml format
  - agr flags and options
  - Claude Code skill commands
  - Cursor skill commands
  - Codex skill commands
  - OpenCode skill commands
  - Copilot skill commands
  - Antigravity skill commands
---

# Reference

!!! tldr
    `agr add` installs skills, `agr sync` installs everything from `agr.toml`,
    `agr config` manages settings. `agrx` runs skills ephemerally. Handles:
    `user/skill`, `user/repo/skill`, or `./local`. Add `-g` for global scope.

Complete reference for all `agr` and [`agrx`](agrx.md) commands. For guided
setup, start with the [Tutorial](tutorial.md).

## Quick Reference

### Install & Remove

```bash
agr add user/skill                     # Install from GitHub
agr add user/repo/skill                # Install from a specific repo
agr add ./path/to/skill                # Install from local directory
agr add user/skill user/other-skill    # Install multiple at once
agr add user/skill --overwrite         # Update to latest version
agr remove user/skill                  # Uninstall a skill
```

### Global Skills

```bash
agr add -g user/skill                  # Install globally (all projects)
agr list -g                            # List global skills
agr sync -g                            # Sync global dependencies
agr remove -g user/skill               # Remove a global skill
```

### Team Sync

```bash
agr sync                               # Install all skills from agr.toml
agr list                               # Show skills and install status
```

### Try Without Installing

```bash
agrx user/skill                        # Run once, then clean up
agrx user/skill -p "Extract tables"    # Pass a prompt
agrx user/skill -i                     # Interactive: skill + chat
agrx user/skill --tool cursor          # Use a specific tool
```

### Create & Share

```bash
agr init my-skill                      # Scaffold a new skill
agr add ./my-skill                     # Test locally
agr add ./my-skill -o                  # Reinstall after editing
```

### Configuration

```bash
agr init                               # Create agr.toml (auto-detects tools)
agr onboard                            # Interactive guided setup
agr config show                        # View current config
agr config set tools claude cursor     # Target multiple tools
agr config set default_tool claude     # Set default for agrx
agr config add tools codex             # Add a tool without replacing
agr config remove tools codex          # Stop syncing to a tool (⚠ deletes its skills)
```

!!! warning "Removing a tool deletes its skills"
    `agr config remove tools <name>` also deletes all skills from that tool's
    skills directory. Skills remain in your other configured tools and can be
    reinstalled with `agr config add tools <name>`.

### Handle Format

```bash
agr add user/skill                 # github.com/user/skills repo, "skill" directory
agr add user/repo/skill            # github.com/user/repo repo, "skill" directory
agr add ./path/to/skill            # Local directory on disk
```

Two-part handles (`user/skill`) assume a repo named `skills`. Use three parts
when the repo has a different name.

### Sources & Private Repos

```bash
export GITHUB_TOKEN="ghp_..."                    # Authenticate for private repos
agr config add sources gitlab \
  --type git --url "https://gitlab.com/{owner}/{repo}.git"   # Custom source
agr add user/skill --source gitlab               # Use a specific source
agr config set default_source gitlab             # Change default source
```

### Instruction Syncing

```bash
agr config set sync_instructions true             # Enable syncing
agr config set canonical_instructions CLAUDE.md   # Set source of truth
agr sync                                          # Copies to AGENTS.md, GEMINI.md
```

## Global Options

- `--quiet`, `-q` — Suppress non-error output (works with all commands)
- `--version`, `-v` — Show version and exit

## CLI Commands

### agr add

Install skills from GitHub or local paths. Skills are installed into your tool's
skills folder (e.g. `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`,
`.opencode/skills/`, `.github/skills/`, `.gemini/skills/`).

If no `agr.toml` exists, `agr add` creates one automatically and detects which
tools you use from repo signals. You don't need to run `agr init` first.

```bash
agr add <handle>...
```

**Arguments:**

- `handle` — Skill handle (`user/skill` or `user/repo/skill`) or local path (`./path`)

**Options:**

- `--overwrite`, `-o` — Replace existing skills
- `--source`, `-s` `<name>` — Use a specific source from `agr.toml`
- `--global`, `-g` — Install globally using `~/.agr/agr.toml` and tool global directories

**Examples:**

```bash
agr add anthropics/skills/frontend-design
agr add -g anthropics/skills/frontend-design
agr add kasperjunge/commit kasperjunge/pr
agr add ./my-skill
agr add anthropics/skills/pdf --overwrite
agr add anthropics/skills/pdf --source github
```

### agr remove

Uninstall skills from all configured tools and remove them from `agr.toml`.
Each skill is deleted from every tool's skills directory (e.g., `.claude/skills/`,
`.cursor/skills/`) and its dependency entry is removed from the manifest.

```bash
agr remove <handle>...
```

**Arguments:**

- `handle` — Skill handle or local path (same formats as `agr add`)

**Options:**

- `--global`, `-g` — Remove from global skills directory and `~/.agr/agr.toml`

**Examples:**

```bash
agr remove anthropics/skills/frontend-design
agr remove -g anthropics/skills/frontend-design
agr remove kasperjunge/commit
agr remove ./my-skill
```

### agr sync

Install all dependencies from `agr.toml`, sync instruction files, and run any
pending directory migrations.

```bash
agr sync
```

```text
Synced instructions: CLAUDE.md -> AGENTS.md
Up to date: anthropics/skills/frontend-design
Up to date: anthropics/skills/pdf
Installed: kasperjunge/commit

Summary: 2 up to date, 1 installed
```

Each `agr sync` run performs up to three stages before reporting results:

1. **Instruction sync** — copies the [canonical instruction file](configuration.md#instruction-syncing) to other tools' instruction files (only when `sync_instructions = true` and 2+ tools are configured)
2. **Migrations** — renames skill directories to match current naming conventions (e.g., Cursor nested → flat, Codex `.codex/` → `.agents/`, OpenCode `.opencode/skill/` → `.opencode/skills/`, Antigravity `.agent/` → `.gemini/`). This happens automatically — no manual steps needed.
3. **Dependency install** — installs any skills from `agr.toml` that are not yet present. Skills from the same repository are batched into a single download.

**Options:**

- `--global`, `-g` — Sync global dependencies from `~/.agr/agr.toml`

### agr list

Show all skills and their installation status.

```bash
agr list
```

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Skill                             ┃ Type   ┃ Status               ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ anthropics/skills/frontend-design │ remote │ installed            │
│ anthropics/skills/pdf             │ remote │ partial (claude)     │
│ kasperjunge/commit                │ remote │ not synced           │
│ ./skills/local-skill              │ local  │ installed            │
└───────────────────────────────────┴────────┴──────────────────────┘
```

**Status values:**

| Status | Meaning |
|--------|---------|
| `installed` | Installed in all configured tools |
| `partial (tool1, tool2)` | Installed in some tools but not all — lists which tools have it |
| `not synced` | Listed in `agr.toml` but not installed in any tool. Run `agr sync` to install. |
| `invalid` | Handle in `agr.toml` cannot be parsed. Check the handle format. |

!!! tip "Partial installs"
    You'll see `partial` status when using [multiple tools](tools.md#target-multiple-tools-at-once)
    and a skill is only installed in some of them. Run `agr sync` to install the
    missing copies, or `agr add <handle> --overwrite` to reinstall everywhere.

**Options:**

- `--global`, `-g` — List global skills from `~/.agr/agr.toml`

### agr init

Create `agr.toml` or a skill scaffold.

```bash
agr init              # Create agr.toml
agr init <name>       # Create skill scaffold
```

`agr init` creates `agr.toml` and auto-detects which tools you use from repo
signals (`.claude/`, `CLAUDE.md`, `.cursor/`, `.cursorrules`, etc.). It does not
discover or add skills — use `agr onboard` for interactive setup with skill
discovery and migration.

**Options:**

- `--tools` — Comma-separated tool list (e.g., `claude,codex,opencode`)
- `--default-tool` — Default tool for `agrx` and instruction sync
- `--sync-instructions/--no-sync-instructions` — Sync instruction files on `agr sync`
- `--canonical-instructions` — Canonical instruction file (`AGENTS.md`, `CLAUDE.md`, or `GEMINI.md`)

**Examples:**

```bash
agr init                    # Creates agr.toml in current directory
agr init my-skill           # Creates my-skill/SKILL.md
agr init --tools claude,codex,opencode --default-tool claude
agr init --sync-instructions --canonical-instructions CLAUDE.md
```

### agr onboard

Interactive guided setup. Walks you through tool selection, skill discovery,
migration from tool folders into `./skills/`, and configuration.

```bash
agr onboard
```

**Options:**

- `--no-migrate` — Skip migration offer for skills in tool folders

**Examples:**

```bash
agr onboard                # Start guided setup
agr onboard --no-migrate   # Skip migration prompts
```

### agr config

Manage `agr.toml` configuration.

```bash
agr config show
```

```text
Config: /Users/you/project/agr.toml

  tools             = claude, codex, opencode
  default_tool      = claude
  default_source    = github
  sync_instructions = true
  canonical_instructions = CLAUDE.md

Sources:
  - github  https://github.com/{owner}/{repo}.git (default)
```

```bash
agr config path
```

```text
/Users/you/project/agr.toml
```

```bash
agr config get tools
```

```text
claude codex opencode
```

**All subcommands:**

```bash
agr config show                              # View formatted config
agr config path                              # Print agr.toml path
agr config edit                              # Open in $VISUAL or $EDITOR
agr config get <key>                         # Read a config value
agr config set <key> <values>                # Write scalar or replace list
agr config add <key> <values>                # Append to list
agr config remove <key> <values>             # Remove from list
agr config unset <key>                       # Clear to default
```

**Valid keys:** `tools`, `default_tool`, `default_source`, `sync_instructions`, `canonical_instructions`, `sources`

**Options (on all subcommands):**

- `--global`, `-g` — Operate on `~/.agr/agr.toml` instead of local

**Options (on `add` only):**

- `--type` — Source type (when key is `sources`)
- `--url` — Source URL (when key is `sources`)

**Examples:**

```bash
agr config set tools claude codex opencode
agr config set default_tool claude
agr config add tools cursor
agr config remove tools cursor            # ⚠ deletes skills from that tool
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
agr config add sources my-source --type git --url "https://git.example.com/{owner}/{repo}.git"
agr config unset default_tool
```

!!! note "Deprecated aliases"
    `agr config tools list/add/set/remove` and `agr config default-tool set/unset` still work but print deprecation warnings. Use the unified commands above instead.

### agrx

Run a skill temporarily without adding to `agr.toml`.

```bash
agrx <handle> [options]
```

Downloads the skill, runs it with the selected tool, and cleans up afterwards.

**Options:**

- `--tool`, `-t` — Tool CLI to use (claude, cursor, codex, opencode, copilot, antigravity). Overrides `default_tool` from config.
- `--interactive`, `-i` — Run skill, then continue in interactive mode
- `--prompt`, `-p` — Prompt to pass to the skill
- `--global`, `-g` — Install to the global tool skills directory instead of the repo-local one
- `--source`, `-s` `<name>` — Use a specific source from `agr.toml`

**Examples:**

```bash
agrx anthropics/skills/pdf
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
agrx kasperjunge/commit -i
agrx kasperjunge/commit --source github
```

## agr.toml Format

```toml
default_source = "github"
tools = ["claude", "codex", "opencode"]
default_tool = "claude"
sync_instructions = true
canonical_instructions = "CLAUDE.md"

dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "kasperjunge/commit", type = "skill"},
    {path = "./local-skill", type = "skill"},
]

[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"
```

Each dependency has:

- `handle` — Remote handle
- `path` — Local path
- `source` — Optional source name for remote handles
- `type` — Currently always `skill`

Note: `dependencies` must appear before any `[[source]]` blocks in `agr.toml`.

### Top-Level Keys

- `default_source` — Name of the default `[[source]]` for remote installs
- `tools` — List of tools to sync instructions/skills to
- `default_tool` — Default tool used by `agrx`
- `sync_instructions` — Sync instruction files on `agr sync`
- `canonical_instructions` — Canonical instruction file (`AGENTS.md`, `CLAUDE.md`, or `GEMINI.md`)

## Troubleshooting

See the [Troubleshooting](troubleshooting.md) page for solutions to common
errors — installation failures, handle format issues, authentication problems,
and more.
