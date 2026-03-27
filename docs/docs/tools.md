---
title: "Install AI Skills in Claude Code, Cursor, Codex, Copilot, OpenCode, and Antigravity"
description: How agr installs skills into Claude Code, Cursor, Codex, GitHub Copilot, OpenCode, and Antigravity — directories, detection, and multi-tool setup.
keywords:
  - agr supported tools
  - Claude Code skills directory
  - Cursor skills setup
  - Codex skills install
  - GitHub Copilot skills
  - OpenCode skills
  - Antigravity skills
  - multi-tool AI setup
  - install skills multiple AI tools
  - agr config set tools
---

# Supported Tools

!!! tldr
    agr installs skills into Claude Code, Cursor, Codex, OpenCode, GitHub
    Copilot, and Antigravity. Target one or all — one `agr add` installs
    everywhere. Default: Claude Code only.

## All Tools at a Glance

| Tool | Config name | Invoke skill | Project skills dir | Global skills dir | agrx CLI |
|------|-------------|-------------|-------------------|-------------------|----------|
| [Claude Code](#claude-code) | `claude` | `/skill-name` | `.claude/skills/` | `~/.claude/skills/` | `claude` |
| [Cursor](#cursor) | `cursor` | `/skill-name` | `.cursor/skills/` | `~/.cursor/skills/` | `agent` |
| [OpenAI Codex](#openai-codex) | `codex` | `$skill-name` | `.agents/skills/` | `~/.agents/skills/` | `codex` |
| [OpenCode](#opencode) | `opencode` | `skill-name` | `.opencode/skills/` | `~/.config/opencode/skills/` | `opencode` |
| [GitHub Copilot](#github-copilot) | `copilot` | `/skill-name` | `.github/skills/` | `~/.copilot/skills/` | `copilot` |
| [Antigravity](#antigravity) | `antigravity` | via IDE | `.gemini/skills/` | `~/.gemini/skills/` | — |

## Target Multiple Tools at Once

By default, agr targets Claude Code only. To install skills into multiple
tools at once:

```bash
agr config set tools claude cursor codex
```

Or during initial setup:

```bash
agr init --tools claude,cursor,codex
```

After this, every `agr add` and `agr sync` installs skills into all configured
tools simultaneously.

---

## Claude Code

[Claude Code](https://claude.ai/download) is Anthropic's AI coding agent that
runs in your terminal.

| | |
|---|---|
| **Config name** | `claude` |
| **Project skills** | `.claude/skills/` |
| **Global skills** | `~/.claude/skills/` |
| **Instruction file** | `CLAUDE.md` |
| **CLI command** | `claude` |
| **Skill invocation** | `/skill-name` |
| **Detection signals** | `.claude/`, `CLAUDE.md` |

Claude Code is the default tool. If you only use Claude Code, no extra
configuration is needed — `agr add` and `agrx` work out of the box.

**Official docs:** [Skills](https://code.claude.com/docs/en/skills) ·
[Slash commands](https://code.claude.com/docs/en/slash-commands) ·
[Sub-agents](https://code.claude.com/docs/en/sub-agents)

---

## Cursor

[Cursor](https://cursor.com) is an AI-first code editor built on VS Code.

| | |
|---|---|
| **Config name** | `cursor` |
| **Project skills** | `.cursor/skills/` |
| **Global skills** | `~/.cursor/skills/` |
| **Instruction file** | `AGENTS.md` |
| **CLI command** | `agent` |
| **Skill invocation** | `/skill-name` |
| **Detection signals** | `.cursor/`, `.cursorrules` |

**Official docs:** [Skills](https://cursor.com/docs/context/skills) ·
[Commands](https://cursor.com/docs/context/commands) ·
[Sub-agents](https://cursor.com/docs/context/subagents) ·
[Rules](https://cursor.com/docs/context/rules)

---

## OpenAI Codex

[OpenAI Codex](https://openai.com/index/introducing-codex/) is OpenAI's
coding agent that runs in your terminal.

| | |
|---|---|
| **Config name** | `codex` |
| **Project skills** | `.agents/skills/` |
| **Global skills** | `~/.agents/skills/` |
| **Instruction file** | `AGENTS.md` |
| **CLI command** | `codex` |
| **Skill invocation** | `$skill-name` |
| **Detection signals** | `.agents/`, `.codex` |

Install the Codex CLI:

```bash
npm i -g @openai/codex
```

**Official docs:** [Skills](https://developers.openai.com/codex/skills) ·
[Custom prompts](https://developers.openai.com/codex/custom-prompts/)

---

## OpenCode

[OpenCode](https://opencode.ai) is an open-source AI coding agent for the
terminal.

| | |
|---|---|
| **Config name** | `opencode` |
| **Project skills** | `.opencode/skills/` |
| **Global skills** | `~/.config/opencode/skills/` |
| **Instruction file** | `AGENTS.md` |
| **CLI command** | `opencode` |
| **Skill invocation** | `skill-name` (no prefix) |
| **Detection signals** | `.opencode/`, `opencode.json`, `opencode.jsonc` |

!!! note "Global path"
    OpenCode uses `~/.config/opencode/skills/` for global skills, which differs
    from the project path pattern (`.opencode/skills/`).

**Official docs:** [Skills](https://opencode.ai/docs/skills) ·
[Commands](https://opencode.ai/docs/commands/) ·
[Agents](https://opencode.ai/docs/agents/)

---

## GitHub Copilot

[GitHub Copilot](https://github.com/features/copilot) is GitHub's AI coding
assistant, available in VS Code, JetBrains, and the CLI.

| | |
|---|---|
| **Config name** | `copilot` |
| **Project skills** | `.github/skills/` |
| **Global skills** | `~/.copilot/skills/` |
| **Instruction file** | `AGENTS.md` |
| **CLI command** | `copilot` |
| **Skill invocation** | `/skill-name` |
| **Detection signals** | `.github/copilot`, `.github/skills` |

!!! note "Asymmetric paths"
    Copilot uses `.github/skills/` for project skills but `~/.copilot/skills/`
    for global skills. agr handles this automatically.

**Official docs:** [Agent skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)

---

## Antigravity

[Antigravity](https://antigravity.dev) is Google's AI coding agent (powered by
Gemini).

| | |
|---|---|
| **Config name** | `antigravity` |
| **Project skills** | `.gemini/skills/` |
| **Global skills** | `~/.gemini/skills/` |
| **Instruction file** | `GEMINI.md` |
| **CLI command** | — (no CLI available) |
| **Skill invocation** | — |
| **Detection signals** | `.gemini/`, `.agent/` |

!!! warning "No CLI support"
    Antigravity does not have a standalone CLI, so `agrx` cannot run skills
    with this tool. Use `agr add` to install skills, then use them through the
    Antigravity interface.

---

## Keep Instruction Files in Sync Across Tools

Each tool uses a different instruction file:

| Instruction file | Tools |
|-----------------|-------|
| `CLAUDE.md` | Claude Code |
| `AGENTS.md` | Cursor, Codex, OpenCode, Copilot |
| `GEMINI.md` | Antigravity |

When you use multiple tools, you can keep these files in sync automatically.
Set a canonical file and agr copies its content to the others on `agr sync`:

```bash
agr config set sync_instructions true
agr config set canonical_instructions CLAUDE.md
```

See [Configuration — Instruction Syncing](configuration.md#instruction-syncing)
for details.

## Add or Remove a Tool After Setup

To start syncing skills to an additional tool:

```bash
agr config add tools cursor
```

This automatically installs all existing dependencies into the new tool — no
separate `agr sync` needed.

To stop syncing to a tool:

```bash
agr config remove tools cursor
```

!!! warning "This deletes installed skills"
    Removing a tool also deletes all skills from that tool's skills directory
    (e.g., `.cursor/skills/`). The skills remain installed in your other
    configured tools and can be reinstalled with `agr config add tools cursor`.

??? note "How agr auto-detects your tools"
    When you run `agr init` or `agr onboard`, agr detects which tools you use
    by looking for their config directories and instruction files in your repo
    (`.claude/`, `CLAUDE.md`, `.cursor/`, `.cursorrules`, etc.). Override with
    `--tools`:

    ```bash
    agr init --tools claude,codex,opencode
    ```

??? note "One skill format works in every tool"
    All tools use the same skill format — a directory containing a `SKILL.md`
    file with YAML frontmatter. A skill written for one tool works in all the
    others. When you `agr add` a skill, the same files are copied into each
    configured tool's skills directory. See the
    [Agent Skills Specification](https://agentskills.io/specification) for full
    format details.

---

## Next Steps

- [Configuration](configuration.md) — Multi-tool setup, custom sources, instruction syncing
- [Creating Skills](creating.md) — Write skills that work across all tools
- [Teams](teams.md) — Set up multi-tool teams with shared skills
