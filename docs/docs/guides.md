---
title: Guides
---

# Guides

Practical recipes for common workflows. Each section answers a specific
question you'll hit after getting started.

---

## Updating Skills

agr doesn't have a dedicated `update` command — skills are updated by
reinstalling them:

```bash
agr add user/skill --overwrite
```

The `--overwrite` flag replaces the installed skill with the latest version
from GitHub.

To update all skills in your project at once, remove and re-sync:

```bash
agr remove user/skill-a user/skill-b
agr sync
```

Or reinstall everything from scratch:

```bash
# Remove all installed skill directories, then reinstall
agr sync
```

!!! tip "Check what's installed"
    Run `agr list` to see all tracked skills and whether they're currently
    installed.

---

## Setting Up a Team

agr uses `agr.toml` as a lockfile-like manifest. Commit it to version control
so the whole team shares the same skills.

### 1. Initialize

```bash
agr init --tools claude,cursor
```

### 2. Add the skills your team needs

```bash
agr add anthropics/skills/frontend-design
agr add anthropics/skills/pdf
agr add ./skills/internal-review   # Local skills work too
```

### 3. Commit `agr.toml`

```bash
git add agr.toml
git commit -m "Add agr skill dependencies"
```

### 4. Teammates install

After cloning the repo, teammates run:

```bash
uv tool install agr   # One-time install (or: pipx install agr)
agr sync              # Install all skills from agr.toml
```

That's it — everyone has the same skills in their tool.

### Multi-tool teams

If your team uses different tools, configure all of them:

```bash
agr config set tools claude cursor codex
```

When anyone runs `agr add` or `agr sync`, skills are installed into every
configured tool's skills directory simultaneously.

---

## CI/CD Integration

Add `agr sync` to your CI pipeline to ensure skills are available in automated
environments.

### GitHub Actions example

```yaml
- name: Install agr
  run: uv tool install agr

- name: Sync skills
  run: agr sync
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}  # For private repos
```

### Private skills in CI

If your team uses private skill repos, the CI runner needs a token:

1. Create a fine-grained GitHub token with **Contents: Read-only** on your
   skill repositories
2. Add it as a repository secret (e.g., `SKILL_TOKEN`)
3. Pass it as `GITHUB_TOKEN`:

```yaml
- name: Sync skills
  run: agr sync
  env:
    GITHUB_TOKEN: ${{ secrets.SKILL_TOKEN }}
```

---

## Discovering Skills

### Browse existing skills

The [anthropics/skills](https://github.com/anthropics/skills) repo contains
official skills maintained by Anthropic.

Community skills are published on individual GitHub accounts. To try one
without installing:

```bash
agrx user/skill-name
```

### List skills in a repository

Use the Python SDK to list all skills in any repo:

```python
from agr import list_skills

for info in list_skills("anthropics/skills"):
    print(f"{info.handle}: {info.description}")
```

Or check a repo manually — agr looks for any directory containing a `SKILL.md`
file.

### Get details about a skill

```python
from agr import skill_info

info = skill_info("anthropics/skills/frontend-design")
print(info.description)
```

---

## Managing Global vs Local Skills

**Local skills** (default) are project-specific. They live in the project's
tool directory (e.g., `.claude/skills/`) and are tracked in `./agr.toml`.

**Global skills** are available everywhere. They live in your home directory
(e.g., `~/.claude/skills/`) and are tracked in `~/.agr/agr.toml`.

### When to use global

Use global skills for personal utilities you want in every project:

```bash
agr add -g anthropics/skills/skill-creator
agr add -g kasperjunge/commit
```

### When to use local

Use local skills for project-specific needs that teammates should share:

```bash
agr add anthropics/skills/frontend-design
```

### Managing both

```bash
agr list          # Show local skills
agr list -g       # Show global skills
agr sync          # Sync local
agr sync -g       # Sync global
```

Global and local skills don't conflict — they live in separate directories.

---

## Using Custom Git Sources

By default, agr fetches from GitHub. You can add other Git hosts:

### GitLab

```bash
agr config add sources gitlab --type git --url "https://gitlab.com/{owner}/{repo}.git"
```

### Self-hosted

```bash
agr config add sources internal --type git --url "https://git.company.com/{owner}/{repo}.git"
```

### Using a custom source

```bash
agr add team/internal-skill --source internal
```

### Making it the default

```bash
agr config set default_source internal
```

Now `agr add team/skill` fetches from your internal server instead of GitHub.

### Per-dependency pinning

Pin specific skills to specific sources in `agr.toml`:

```toml
dependencies = [
    {handle = "team/internal-skill", type = "skill", source = "internal"},
    {handle = "anthropics/skills/pdf", type = "skill"},
]
```

---

## Migrating from Manual Skill Management

If you've been copying SKILL.md files manually or managing skills outside of
agr:

### 1. Initialize agr

```bash
agr init
```

### 2. Use the interactive onboard

```bash
agr onboard
```

This walks you through:

- Selecting which tools you use
- Discovering skills already in your tool directories
- Migrating them into `./skills/` as local dependencies
- Creating your `agr.toml`

### 3. Convert old rules or commands to skills

If you have `.claude/commands/`, `.cursorrules`, or similar files that should
become skills:

```bash
agrx kasperjunge/migrate-to-skills
```

This analyzes your existing files and converts them to the SKILL.md format.
