---
title: "Configure agr.toml — Multi-Tool Setup, Sources, and Instruction Syncing"
description: Configure agr.toml for multi-tool setup across Claude Code, Cursor, Codex, OpenCode, Copilot, and Antigravity — custom Git sources, instruction syncing, and global installs.
keywords:
  - agr.toml configuration
  - agr config command
  - custom git sources
  - private repository skills
  - global skill install
  - instruction syncing
  - multi-tool AI setup
  - agr config set tools
  - Claude Code agr config
  - Cursor agr setup
  - Codex agr config
  - OpenCode agr setup
  - GitHub Copilot agr config
  - Antigravity agr setup
---

# Configuration

!!! tldr
    `agr.toml` is your skill manifest. Key settings: **tools** (which AI tools
    to sync to), **sources** (where to fetch skills from), **sync_instructions**
    (keep `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` aligned). Use `agr config` to
    manage everything from the CLI. Add `-g` for global config at `~/.agr/agr.toml`.

agr uses `agr.toml` for project-level configuration and `~/.agr/agr.toml` for
global configuration. For an overview of how config fits into agr's architecture,
see [Core Concepts](concepts.md).

## Settings at a Glance

| Key | Type | Default | What it does |
|-----|------|---------|-------------|
| `tools` | list | `["claude"]` | [AI tools](#multi-tool-setup) to install skills into |
| `default_tool` | string | first in `tools` | Tool used by [`agrx`](agrx.md) and for [instruction sync](#instruction-syncing) |
| `default_source` | string | `"github"` | [Source](#sources) used when `--source` is not specified |
| `sync_instructions` | bool | `false` | Copy the canonical instruction file to other tools on [`agr sync`](reference.md#agr-sync) |
| `canonical_instructions` | string | auto from `default_tool` | Which [instruction file](#instruction-syncing) is the source of truth (`CLAUDE.md`, `AGENTS.md`, or `GEMINI.md`) |

Dependencies and sources are configured separately — see [Full Example](#full-agrtoml-example) below.

## Multi-Tool Setup

By default, agr targets Claude Code only. To install skills into multiple tools
at once, configure the `tools` list:

```bash
agr init --tools claude,codex,opencode
```

Or update an existing config:

```bash
agr config set tools claude codex opencode cursor
```

When you run `agr add` or `agr sync`, skills are installed into every configured
tool's skills directory:

| Tool | Project skills directory | Global skills directory |
|------|------------------------|------------------------|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| OpenAI Codex | `.agents/skills/` | `~/.agents/skills/` |
| OpenCode | `.opencode/skills/` | `~/.config/opencode/skills/` |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` |
| Antigravity | `.gemini/skills/` | `~/.gemini/skills/` |

### Default Tool

The default tool determines which CLI is used by `agrx` and which instruction
file is canonical when syncing:

```bash
agr config set default_tool claude
```

If not set, the first tool in the `tools` list is used.

### Adding and Removing Tools

Add a tool after initial setup — existing skills are installed into it
automatically:

```bash
agr config add tools cursor
```

!!! warning "Removing a tool deletes its skills"
    `agr config remove tools <name>` deletes all skills from that tool's skills
    directory. Skills remain in your other tools and can be reinstalled with
    `agr config add tools <name>`.

### Tool Detection

`agr init` and `agr onboard` auto-detect tools from repo signals — config
directories (`.claude/`, `.cursor/`, `.agents/`, `.gemini/`) and instruction files
(`CLAUDE.md`, `.cursorrules`).

## Sources

Sources define where agr fetches remote skills from. The default source is
GitHub:

```toml
[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"
```

### Adding a Custom Source

To fetch skills from a self-hosted Git server:

```bash
agr config add sources my-server --type git --url "https://git.example.com/{owner}/{repo}.git"
```

The URL template uses `{owner}` and `{repo}` placeholders, which are filled from
the handle. For example, `agr add user/repo/skill --source my-server` clones
`https://git.example.com/user/repo.git`.

!!! note "Only `git` type is supported"
    The `--type` flag currently only accepts `git`. Other source types may be
    added in the future.

### Default Source

Set which source is tried first for remote installs:

```bash
agr config set default_source my-server
```

!!! warning "Cannot remove the default source"
    You can't remove a source that is set as `default_source`. Change the
    default first, then remove the source:
    ```bash
    agr config set default_source github
    agr config remove sources my-server
    ```

### Per-Dependency Source

Pin a specific dependency to a source in `agr.toml`:

```toml
dependencies = [
    {handle = "team/internal-skill", type = "skill", source = "my-server"},
    {handle = "anthropics/skills/pdf", type = "skill"},
]
```

## Instruction Syncing

When using multiple tools, you may want to keep instruction files
(`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) in sync. Enable this with:

```bash
agr init --sync-instructions --canonical-instructions CLAUDE.md
```

Or configure it directly:

```bash
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
```

When `agr sync` runs, it copies the canonical file's content to the other
instruction files needed by your configured tools. For example, with
`canonical_instructions = "CLAUDE.md"` and `tools = ["claude", "codex"]`, running
`agr sync` copies `CLAUDE.md` content to `AGENTS.md` (used by Codex).

!!! important "Requires 2+ tools"
    Instruction syncing only runs when you have **two or more tools** configured.
    With a single tool there's nothing to sync to, so `agr sync` silently skips
    this step — even if `sync_instructions = true`.

### Auto-detection of canonical file

If you set `sync_instructions = true` but don't set `canonical_instructions`,
agr picks the instruction file of your **default tool** (or the first tool in
your `tools` list). For example, if your default tool is `claude`, the canonical
file is `CLAUDE.md`.

To be explicit, set it yourself:

```bash
agr config set canonical_instructions CLAUDE.md
```

## Private Repositories

agr supports private GitHub repositories. Set a GitHub personal access token in
your environment and agr will use it automatically for all remote operations.

### Setup

Export one of these environment variables:

```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

Or, if you use the [GitHub CLI](https://cli.github.com/):

```bash
export GH_TOKEN="$(gh auth token)"
```

agr checks `GITHUB_TOKEN` first, then falls back to `GH_TOKEN`.

### How It Works

When a `GITHUB_TOKEN` or `GH_TOKEN` is set, agr injects the token into HTTPS
clone URLs for GitHub sources. This happens transparently — no config changes
needed. The token is used for:

- `agr add` — cloning private repos
- `agr sync` — syncing private dependencies
- `agrx` — ephemeral runs from private repos
- Python SDK — `Skill.from_git()`, `list_skills()`, `skill_info()`

### Token Permissions

The token needs **read access** to the repositories containing your skills:

- **Fine-grained tokens** (recommended): Grant `Contents: Read-only` on the
  specific repositories
- **Classic tokens**: The `repo` scope works but grants broader access

### Per-Shell vs Permanent

Add the export to your shell profile for permanent access:

=== "bash"

    ```bash
    echo 'export GITHUB_TOKEN="ghp_your_token"' >> ~/.bashrc
    ```

=== "zsh"

    ```bash
    echo 'export GITHUB_TOKEN="ghp_your_token"' >> ~/.zshrc
    ```

Or use a secrets manager and load it dynamically:

```bash
export GITHUB_TOKEN="$(gh auth token)"
```

### Non-GitHub Sources

Token injection only applies to GitHub URLs. For self-hosted Git servers, embed
credentials in the source URL or configure them through your system's Git
credential helper:

```bash
git config --global credential.helper store
```

## Global Installs

Skills can be installed globally (available in all projects) using the `-g` flag:

```bash
agr add -g anthropics/skills/pdf
agr sync -g
agr list -g
agr remove -g anthropics/skills/pdf
```

Global configuration lives at `~/.agr/agr.toml` and skills are installed into
each tool's global skills directory (see table above).

## Full agr.toml Example

```toml
default_source = "github"
tools = ["claude", "codex", "opencode"]
default_tool = "claude"
sync_instructions = true
canonical_instructions = "CLAUDE.md"

dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "kasperjunge/commit", type = "skill"},
    {handle = "team/internal-tool", type = "skill", source = "my-server"},
    {path = "./skills/local-skill", type = "skill"},
]

[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"

[[source]]
name = "my-server"
type = "git"
url = "https://git.example.com/{owner}/{repo}.git"
```

!!! note "Ordering"
    `dependencies` must appear before any `[[source]]` blocks in `agr.toml`.

## Managing Config

All config operations use the `agr config` command:

```bash
agr config show               # View formatted config
agr config path               # Print agr.toml path
agr config edit               # Open in $VISUAL or $EDITOR
agr config get <key>           # Read a value
agr config set <key> <values>  # Write a value
agr config add <key> <values>  # Append to a list
agr config remove <key> <values>  # Remove from a list
agr config unset <key>         # Clear to default
```

Add `-g` to any command to operate on the global config (`~/.agr/agr.toml`).

!!! note "`agr config edit` requires an editor"
    `agr config edit` opens `agr.toml` in your `$VISUAL` (or `$EDITOR`).
    If neither environment variable is set, you'll get an error. Set one:
    ```bash
    export EDITOR="vim"              # or nano, code --wait, etc.
    ```

See the [CLI Reference](reference.md) for full details.

## Next Steps

- [**Supported Tools**](tools.md) — Details on each tool's skills directory and behavior
- [**Teams**](teams.md) — Set up multi-tool teams with shared skills and CI/CD
- [**Troubleshooting**](troubleshooting.md) — Fix common config and sync issues
