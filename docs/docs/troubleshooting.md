---
title: Troubleshooting
description: Fix common agr problems — installation errors, GitHub auth, sync failures, and skill conflicts.
keywords:
  - agr troubleshooting
  - agr errors
  - GitHub authentication
  - skill sync failures
  - agr not working
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
```

The repo exists but doesn't contain a skill with that name. agr searches recursively for a directory matching the skill name that contains a `SKILL.md` file.

**Fix:** Check the repo on GitHub to see what skills are available. If you used a two-part handle, agr may suggest corrections:

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

Skill names cannot contain `--`. Rename the skill to use single hyphens.

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

### How do I fix "Invalid TOML in agr.toml"?

```text
Error: Invalid TOML in agr.toml: ...
```

Your `agr.toml` has a syntax error. Common causes:

- **Missing quotes** around string values
- **Unclosed brackets** in `dependencies` or `[[source]]`
- **Trailing commas** after the last item in a list (TOML doesn't allow them)

Validate with any TOML linter, or paste your file into [toml-lint.com](https://www.toml-lint.com/) to find the exact line.

### "default_tool must be listed in tools"

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

### "default_source not found in [[source]] list"

```text
Error: default_source 'my-server' not found in [[source]] list
```

Your `default_source` refers to a source that doesn't exist. Either add the source or fix the name:

```bash
agr config add sources my-server --type git --url "https://git.example.com/{owner}/{repo}.git"
# or fix the default
agr config set default_source github
```

### "dependencies must be declared before [[source]] blocks"

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

### "Unknown source in dependency"

```text
Error: Unknown source 'gitlab' in dependency 'user/skill'
```

A dependency in `agr.toml` specifies a `source` that isn't defined in your `[[source]]` list. Either add the source or remove the `source` field from the dependency:

```bash
# Add the missing source
agr config add sources gitlab --type git --url "https://gitlab.com/{owner}/{repo}.git"

# Or edit agr.toml and remove source = "gitlab" from the dependency
```

### "canonical_instructions must be 'AGENTS.md', 'CLAUDE.md', or 'GEMINI.md'"

Only these three instruction file names are supported for syncing. Other filenames like `README.md` or `INSTRUCTIONS.md` won't work.

---

## Syncing

### "No dependencies in agr.toml. Nothing to sync."

Your `agr.toml` exists but has no `dependencies` entry. Add skills first:

```bash
agr add user/skill
```

This both installs the skill and adds it to `agr.toml`.

### "Instruction sync skipped: CLAUDE.md not found."

You have `sync_instructions = true` but the canonical instruction file doesn't exist yet. Create it:

```bash
touch CLAUDE.md
```

Then run `agr sync` again.

### Instruction sync enabled but nothing happens

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

### Sync shows "Up to date" but skill seems outdated

`agr sync` skips skills that are already installed. To force a fresh install from
the latest version:

```bash
agr add user/skill --overwrite
```

This re-downloads the skill from GitHub and replaces your local copy.

---

## Sources

### "Cannot remove default source"

```text
Error: Cannot remove default source 'my-server'. Change the default source first.
```

You can't remove a source that is currently set as `default_source`. Change the
default first:

```bash
agr config set default_source github
agr config remove sources my-server
```

### "Local skills cannot specify a source"

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

### "Invalid skill name"

```text
Error: Invalid skill name 'my skill': must be alphanumeric with hyphens/underscores
```

Skill names must be alphanumeric with hyphens or underscores, and must start with a letter or number. No spaces or special characters:

```bash
# Wrong
agr init "my skill"
agr init "My Skill!"

# Right
agr init my-skill
agr init my_skill
agr init MySkill
```

### "Directory already exists"

```text
Error: Directory 'myskill' already exists
```

`agr init` won't overwrite an existing directory. Either remove it or choose a different name.

### Skill not showing up in my tool

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

### "No global agr.toml found"

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

## Still stuck?

- Run the failing command with details and check the output carefully — agr prints hints below most errors.
- Check [GitHub Issues](https://github.com/kasperjunge/agent-resources/issues) for known problems.
- [Open a new issue](https://github.com/kasperjunge/agent-resources/issues/new) with the full error output and your `agr.toml` contents.

## Related Pages

- [**Configuration**](configuration.md) — Full `agr.toml` reference and setup options
- [**CLI Reference**](reference.md) — Every command, flag, and option
- [**Creating Skills**](creating.md) — Fix skill authoring issues
