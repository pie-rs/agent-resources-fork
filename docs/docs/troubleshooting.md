---
title: "Fix agr Errors — Troubleshooting Installs, Auth, Sync, Handles, and Skills"
description: Fix common agr problems — installation errors, GitHub auth, sync failures, handle formats, skill conflicts, and configuration issues.
keywords:
  - agr troubleshooting
  - agr error messages
  - fix agr not working
  - GitHub authentication failed agr
  - agr sync not working
  - skill not found agr
  - agr.toml errors
  - agr handle format
  - agr repository not found
  - agr permission error private repo
  - agr config error fix
  - agrx tool CLI not found
  - agr skill already exists
  - agr invalid handle format
  - agr git not found
---

# Troubleshooting

Common problems and how to fix them.

## Installation

### How do I fix "git CLI not found"?

```text
Error: git CLI not found. Install git to fetch remote skills.
```

agr uses `git` under the hood for all remote operations. Install it:

=== "macOS"

    ```bash
    xcode-select --install
    ```

=== "Ubuntu/Debian"

    ```bash
    sudo apt install git
    ```

=== "Windows"

    Download from [git-scm.com](https://git-scm.com/downloads).

### How do I fix "Repository not found"?

```text
Error: Repository 'user/skills' not found in source 'github'.
```

The repository doesn't exist or is private. Check:

1. **Typo in the handle?** Verify the username and repo name on GitHub.
2. **Private repo?** Set a GitHub token (see [Private Repositories](configuration.md#private-repositories)):
   ```bash
   export GITHUB_TOKEN="ghp_your_token_here"
   ```
3. **Non-default repo name?** Use the three-part handle format:
   ```bash
   agr add user/my-custom-repo/skill-name
   ```

### How do I fix "Authentication failed"?

```text
Error: Authentication failed for source 'github'.
```

Your GitHub token is missing, expired, or lacks permissions.

- **No token set?** Export one:
  ```bash
  export GITHUB_TOKEN="ghp_your_token_here"
  # or
  export GH_TOKEN="$(gh auth token)"
  ```
- **Token expired?** Generate a new one at [github.com/settings/tokens](https://github.com/settings/tokens).
- **Wrong permissions?** The token needs **Contents: Read-only** access on the target repository. Fine-grained tokens are recommended.

### How do I fix "Skill not found in repository"?

```text
Error: Skill 'myskill' not found in repository.
No directory named 'myskill' containing SKILL.md was found.
Hint: Create a skill at 'skills/myskill/SKILL.md' or 'myskill/SKILL.md'
```

The repo exists but doesn't contain a skill with that name. agr searches recursively for a directory matching the skill name that contains a `SKILL.md` file.

**Fix:** Follow the hint to create the skill, or check the repo on GitHub to see what skills are available. If you used a two-part handle, agr may suggest corrections:

```text
Skill 'myskill' not found. However, 'user/myskill' exists as a repository with 3 skill(s):
  agr add user/myskill/skill1
  agr add user/myskill/skill2
  agr add user/myskill/skill3
```

### How do I fix "Skill already exists"?

```text
Error: Skill already exists at /path/to/skill. Use --overwrite to replace.
```

The skill is already installed. To update it:

```bash
agr add user/skill --overwrite
```

Or remove it first:

```bash
agr remove user/skill
agr add user/skill
```

### How do I fix "Network error: could not resolve host"?

```text
Error: Network error: could not resolve host for source 'github'.
```

DNS resolution failed. Check your internet connection, VPN, or proxy settings.

---

## Handle Format

### How do I fix "Invalid handle: remote handles require username/name format"?

```text
Error: Invalid handle 'commit': remote handles require username/name format
```

A single word is treated as a local path. For remote skills, use the [handle format](concepts.md#handles):

```bash
# Wrong
agr add commit

# Right
agr add kasperjunge/commit
```

### How do I fix "Too many path segments"?

```text
Error: Invalid handle 'a/b/c/d': too many path segments (expected user/name or user/repo/name)
```

Handles support at most three parts: `user/repo/skill`. Check for extra slashes.

### How do I fix "Contains reserved sequence '--'"?

```text
Error: Invalid handle 'user/my--skill': skill name 'my--skill' contains reserved sequence '--'
```

Skill names cannot contain consecutive hyphens. Rename the skill to use single hyphens (e.g., `my-skill` instead of `my--skill`).

---

## Configuration

### How do I fix "No agr.toml found"?

```text
Error: No agr.toml found.
Run 'agr init' first to create one.
```

You're running a command that requires `agr.toml` but the file doesn't exist yet. Create one:

```bash
agr init
```

Or use interactive setup:

```bash
agr onboard
```

### How do I fix "Not in a git repository"?

```text
Error: Not in a git repository
```

Project-level commands need to run inside a git repo. Either `cd` into one or initialize git:

```bash
git init
```

For `agrx`, use `--global` to run outside a git repo:

```bash
agrx anthropics/skills/pdf --global
```

### How do I fix "Unknown tool"?

```text
Error: Unknown tool 'photoshop' in agr.toml. Available: claude, cursor, codex, opencode, copilot, antigravity
```

Check your `agr.toml` for typos in the `tools` list. See [Supported Tools](tools.md) for details on each:

| Config name | Tool |
|-------------|------|
| `claude` | Claude Code |
| `cursor` | Cursor |
| `codex` | OpenAI Codex |
| `opencode` | OpenCode |
| `copilot` | GitHub Copilot |
| `antigravity` | Antigravity |

### Why does `agr init` detect a tool I don't use?

`agr init` and `agr onboard` auto-detect tools by looking for specific files and
directories in your repo. Some detection signals are shared between tools:

| Signal | Detected tools |
|--------|---------------|
| `.agents/` | OpenAI Codex **and** Antigravity |

For example, if you use Codex and have an `.agents/` directory, agr also detects
Antigravity because both tools use that directory. This is intentional — the
`.agents/` path follows the [Agent Skills spec](https://agentskills.io/specification)
and both tools read skills from it.

To override detection and pick only the tools you want:

```bash
agr init --tools claude,codex
```

Or remove unwanted tools after setup:

```bash
agr config remove tools antigravity
```

See [Supported Tools — Detection signals](tools.md) for the full list per tool.

### How do I fix "Invalid TOML in agr.toml"?

```text
Error: Invalid TOML in agr.toml: ...
```

Your `agr.toml` has a syntax error. Common causes:

- **Missing quotes** around string values
- **Unclosed brackets** in `dependencies` or `[[source]]`
- **Trailing commas** after the last item in a list (TOML doesn't allow them)

Validate with any TOML linter, or paste your file into [toml-lint.com](https://www.toml-lint.com/) to find the exact line.

### How do I fix "default_tool must be listed in tools"?

```text
Error: default_tool must be listed in tools in agr.toml
```

Your `default_tool` value isn't in your `tools` list. Either add it to `tools` or change `default_tool`:

```toml
# Wrong — codex isn't in tools
tools = ["claude", "cursor"]
default_tool = "codex"
```

```toml
# Right
tools = ["claude", "cursor", "codex"]
default_tool = "codex"
```

### How do I fix "default_source not found in [[source]] list"?

```text
Error: default_source 'my-server' not found in [[source]] list
```

Your `default_source` refers to a source that doesn't exist. Either add the source or fix the name:

```bash
agr config add sources my-server --type git --url "https://git.example.com/{owner}/{repo}.git"
# or fix the default
agr config set default_source github
```

### How do I fix "dependencies must be declared before [[source]] blocks"?

```text
Error: dependencies must be declared before [[source]] blocks
```

In `agr.toml`, the `dependencies` array must come before any `[[source]]` entries:

```toml
# Correct order
dependencies = [
    {handle = "user/skill", type = "skill"},
]

[[source]]
name = "github"
type = "git"
url = "https://github.com/{owner}/{repo}.git"
```

### How do I fix "Unknown source in dependency"?

```text
Error: Unknown source 'gitlab' in dependency 'user/skill'
```

A dependency in `agr.toml` specifies a `source` that isn't defined in your `[[source]]` list. Either add the source or remove the `source` field from the dependency:

```bash
# Add the missing source
agr config add sources gitlab --type git --url "https://gitlab.com/{owner}/{repo}.git"

# Or edit agr.toml and remove source = "gitlab" from the dependency
```

### How do I fix "Dependency cannot have both handle and path"?

```text
Error: Dependency cannot have both handle and path
```

A dependency in `agr.toml` has both a `handle` and a `path` field. Each
dependency must use one or the other:

```toml
# Wrong — both handle and path
dependencies = [
    {handle = "user/skill", path = "./skills/skill", type = "skill"},
]
```

```toml
# Right — remote
dependencies = [
    {handle = "user/skill", type = "skill"},
]
```

```toml
# Right — local
dependencies = [
    {path = "./skills/skill", type = "skill"},
]
```

### How do I fix "Dependency must have either handle or path"?

```text
Error: Dependency must have either handle or path
```

A dependency in `agr.toml` is missing both `handle` and `path`. Every dependency
needs one:

```toml
# Wrong — no handle or path
dependencies = [
    {type = "skill"},
]
```

```toml
# Right
dependencies = [
    {handle = "user/skill", type = "skill"},
]
```

### How do I fix "canonical_instructions must be 'AGENTS.md', 'CLAUDE.md', or 'GEMINI.md'"?

Only these three instruction file names are supported for syncing. Other filenames like `README.md` or `INSTRUCTIONS.md` won't work.

---

## Syncing

### How do I fix "No dependencies in agr.toml. Nothing to sync."?

Your `agr.toml` exists but has no `dependencies` entry. Add skills first:

```bash
agr add user/skill
```

This both installs the skill and adds it to `agr.toml`.

### How do I fix "Instruction sync skipped: CLAUDE.md not found."?

You have `sync_instructions = true` but the canonical instruction file doesn't exist yet. Create it:

```bash
touch CLAUDE.md
```

Then run `agr sync` again.

### Why does instruction sync not do anything?

You have `sync_instructions = true` but `agr sync` doesn't copy any instruction
files. Two common causes:

1. **Only one tool configured.** Instruction syncing requires **two or more
   tools** — with a single tool, there's nothing to sync to. Add another tool:
   ```bash
   agr config set tools claude cursor
   agr sync
   ```

2. **All tools use the same instruction file.** If all your configured tools
   share the same instruction file (e.g., Cursor, Codex, and OpenCode all use
   `AGENTS.md`), there's nothing to copy. Syncing only helps when tools need
   *different* instruction files (e.g., Claude uses `CLAUDE.md`, Codex uses
   `AGENTS.md`).

### Why does sync show "Up to date" but my skill seems outdated?

`agr sync` skips skills that are already installed. To force a fresh install from
the latest version:

```bash
agr add user/skill --overwrite
```

This re-downloads the skill from GitHub and replaces your local copy.

---

## Sources

### How do I fix "Cannot remove default source"?

```text
Error: Cannot remove default source 'my-server'. Change the default source first.
```

You can't remove a source that is currently set as `default_source`. Change the
default first:

```bash
agr config set default_source github
agr config remove sources my-server
```

### How do I fix "Source entry missing name"?

```text
Error: Source entry missing name
```

A `[[source]]` block in your `agr.toml` is missing the `name` field. Every source needs a name:

```toml
# Wrong — missing name
[[source]]
type = "git"
url = "https://git.example.com/{owner}/{repo}.git"

# Right
[[source]]
name = "my-server"
type = "git"
url = "https://git.example.com/{owner}/{repo}.git"
```

### How do I fix "Source missing url"?

```text
Error: Source 'my-server' missing url
```

A `[[source]]` block has a name but no `url`. Add the URL template:

```toml
[[source]]
name = "my-server"
type = "git"
url = "https://git.example.com/{owner}/{repo}.git"
```

### How do I fix "Unsupported source type"?

```text
Error: Unsupported source type 'svn' for 'my-server'
```

Only `git` sources are supported. Change the `type` to `git`:

```toml
[[source]]
name = "my-server"
type = "git"
url = "https://git.example.com/{owner}/{repo}.git"
```

### How do I fix "GitHub API rate limit exceeded"?

```text
Error: GitHub API rate limit exceeded
```

You've hit GitHub's API rate limit. This mainly affects the Python SDK (`list_skills()`, `skill_info()`) which use the GitHub API — not `agr add` or `agr sync`, which use Git clones.

- **Authenticate to raise your limit.** Unauthenticated requests are limited to 60/hour. With a token, you get 5,000/hour:
  ```bash
  export GITHUB_TOKEN="ghp_your_token_here"
  ```
- **Wait for the limit to reset.** GitHub rate limits reset hourly. Check your remaining quota with:
  ```bash
  curl -s -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/rate_limit | python3 -m json.tool
  ```
- **In CI, cache results.** If your pipeline calls `list_skills()` or `skill_info()` repeatedly, cache the output instead of calling the API on every run.

### How do I fix "Local skills cannot specify a source"?

```text
Error: Local skills cannot specify a source
```

The `--source` flag only applies to remote handles. Local paths (`./my-skill`)
are installed directly from disk — they don't go through any source:

```bash
# Wrong
agr add ./my-skill --source github

# Right
agr add ./my-skill
```

---

## Creating Skills

### How do I fix "Invalid skill name"?

```text
Error: Invalid skill name 'My_Skill': must be 1-64 lowercase alphanumeric characters and hyphens, cannot start/end with a hyphen
```

Skill names must be lowercase alphanumeric with hyphens. No uppercase, underscores, spaces, or special characters. Names cannot start or end with a hyphen, and consecutive hyphens (`--`) are not allowed.

```bash
# Wrong
agr init "my skill"
agr init My_Skill
agr init MySkill
agr init -my-skill

# Right
agr init my-skill
agr init myskill
agr init code-reviewer
```

### How do I fix "Directory already exists"?

```text
Error: Directory 'myskill' already exists
```

`agr init` won't overwrite an existing directory. Either remove it or choose a different name.

### How do I fix "Local skill name is already installed"?

```text
Error: Local skill name 'my-skill' is already installed at /path/to/my-skill.
agr allows only one local skill with a given name.
Rename the skill or remove the existing one.
```

You have two local skills with the same name. agr enforces unique names to avoid conflicts. Either rename one of the skills or remove the existing one:

```bash
agr remove my-skill
agr add ./new-location/my-skill
```

### How do I fix "not a valid skill (missing SKILL.md)"?

```text
Error: './my-skill' is not a valid skill (missing SKILL.md)
```

The path you specified doesn't contain a `SKILL.md` file. Every skill needs one:

```bash
# Create the required file
touch my-skill/SKILL.md
```

Then add the required frontmatter (`name` and `description`) — see [Creating Skills](creating.md).

### Why is my skill not showing up in my tool?

After `agr add ./skills/my-skill`, verify:

1. **Check the skill directory exists** in the tool's skills folder (e.g., `.claude/skills/my-skill/SKILL.md`).
2. **Validate SKILL.md frontmatter** — both `name` and `description` are required:
   ```markdown
   ---
   name: my-skill
   description: What this skill does and when to use it.
   ---
   ```
3. **Restart the tool** — some tools require a restart to pick up new skills.
4. **Check `agr list`** to see if the skill is registered.

---

## Global Installs

### How do I fix "No global agr.toml found"?

```text
Error: No global agr.toml found
Run 'agr add -g <handle>' first.
```

There's no global config yet. Install a skill globally to create one:

```bash
agr add -g user/skill
```

The global config lives at `~/.agr/agr.toml`.

---

## agrx

### How do I fix "Tool CLI not found"?

```text
Error: Tool CLI 'codex' not found. Install it to use agrx.
```

`agrx` needs the selected tool's CLI installed on your system. See which CLI each tool requires:

| Tool | CLI command | Install |
|------|------------|---------|
| Claude Code | `claude` | [claude.ai/download](https://claude.ai/download) |
| Cursor | `agent` | Install the Cursor IDE |
| OpenAI Codex | `codex` | `npm i -g @openai/codex` |
| OpenCode | `opencode` | [opencode.ai](https://opencode.ai) |
| GitHub Copilot | `copilot` | Install GitHub Copilot CLI |

If you have the tool installed but `agrx` can't find it, check that the CLI is on your `PATH`:

```bash
which claude   # or codex, agent, opencode, copilot
```

### How do I fix "agrx only works with remote handles"?

```text
Error: agrx only works with remote handles
Hint: Use 'agr add' for local skills
```

`agrx` downloads skills from GitHub and cleans up after running — it doesn't
work with local paths. For local skills, install them permanently instead:

```bash
# Wrong
agrx ./skills/my-skill

# Right — install locally
agr add ./skills/my-skill

# Right — run a remote skill
agrx user/my-skill
```

### Why can't I use agrx with Antigravity?

Antigravity does not have a standalone CLI, so `agrx` cannot run skills with it. Use `agr add` to install skills permanently, then invoke them through the Antigravity IDE interface.

### How do I use agrx outside a git repository?

By default, `agrx` requires a git repo (to find `agr.toml` for tool/source config). Use `--global` to skip this:

```bash
agrx anthropics/skills/pdf --global
```

This installs the skill into the tool's global skills directory, runs it, and cleans up.

---

## Still stuck?

- Run the failing command with details and check the output carefully — agr prints hints below most errors.
- Check [GitHub Issues](https://github.com/kasperjunge/agent-resources/issues) for known problems.
- [Open a new issue](https://github.com/kasperjunge/agent-resources/issues/new) with the full error output and your `agr.toml` contents.

## Related Pages

- [**Configuration**](configuration.md) — Fix `agr.toml` settings, sources, and instruction sync issues
- [**Supported Tools**](tools.md) — Check detection signals, skill directories, and CLI requirements per tool
- [**agrx**](agrx.md) — Fix issues with ephemeral skill runs, tool selection, and interactive mode
- [**CLI Reference**](reference.md) — Verify command syntax, flags, and handle formats
- [**Creating Skills**](creating.md) — Fix SKILL.md format, name validation, and testing issues
- [**Teams**](teams.md) — Fix CI/CD sync failures, private repo auth, and multi-tool team setup
