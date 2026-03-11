---
title: Skill Directory
---

# Skill Directory

Browse available skills and find ones that fit your workflow.

---

## Official Skills

Maintained by Anthropic in the [anthropics/skills](https://github.com/anthropics/skills) repository.

| Skill | Install command |
|-------|----------------|
| Frontend Design | `agr add anthropics/skills/frontend-design` |
| PDF | `agr add anthropics/skills/pdf` |
| Skill Creator | `agr add anthropics/skills/skill-creator` |
| MCP Builder | `agr add anthropics/skills/mcp-builder` |

Try any skill without installing:

```bash
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
```

Browse the full list at [github.com/anthropics/skills](https://github.com/anthropics/skills).

---

## Community Skills

Skills built and shared by the community.

### Go

| Skill | Author | Install command |
|-------|--------|----------------|
| Go Pro | [@dsjacobsen](https://github.com/dsjacobsen) | `agr add dsjacobsen/golang-pro` |

### Drupal

| Skill | Author | Install command |
|-------|--------|----------------|
| Drupal Expert | [@madsnorgaard](https://github.com/madsnorgaard) | `agr add madsnorgaard/drupal-agent-resources/drupal-expert` |
| Drupal Security | [@madsnorgaard](https://github.com/madsnorgaard) | `agr add madsnorgaard/drupal-agent-resources/drupal-security` |
| Drupal Migration | [@madsnorgaard](https://github.com/madsnorgaard) | `agr add madsnorgaard/drupal-agent-resources/drupal-migration` |
| DDEV Expert | [@madsnorgaard](https://github.com/madsnorgaard) | `agr add madsnorgaard/drupal-agent-resources/ddev-expert` |
| Docker Local | [@madsnorgaard](https://github.com/madsnorgaard) | `agr add madsnorgaard/drupal-agent-resources/docker-local` |

### Workflow

| Skill | Author | Install command |
|-------|--------|----------------|
| Commit | [@kasperjunge](https://github.com/kasperjunge) | `agr add kasperjunge/commit` |
| PR | [@kasperjunge](https://github.com/kasperjunge) | `agr add kasperjunge/pr` |
| Collaboration | [@maragudk](https://github.com/maragudk) | `agr add maragudk/skills/collaboration` |
| Migrate to Skills | [@kasperjunge](https://github.com/kasperjunge) | `agr add kasperjunge/migrate-to-skills` |

---

## Discovering More Skills

### Browse GitHub

Any GitHub repository with a `SKILL.md` file can be installed with agr. Search GitHub for repositories containing skill files:

- [Search for SKILL.md files on GitHub](https://github.com/search?q=filename%3ASKILL.md&type=code)

### List skills in a repository

Use the Python SDK to list all skills in a repo:

```python
from agr import list_skills

for info in list_skills("anthropics/skills"):
    print(f"{info.handle}: {info.description}")
```

### Try before you install

Use `agrx` to run any skill without adding it to your project:

```bash
agrx user/skill-name
agrx user/skill-name -i   # Interactive: continue chatting after the skill runs
```

---

## Share Your Own Skills

### 1. Create a skill

```bash
agr init my-skill
```

Edit the generated `my-skill/SKILL.md` with your instructions.

### 2. Push to GitHub

Push your skill to a GitHub repository. The recommended structure is a repo named `skills` with one directory per skill:

```
your-username/skills/
├── my-skill/
│   └── SKILL.md
└── another-skill/
    └── SKILL.md
```

Others can then install with:

```bash
agr add your-username/my-skill
```

### 3. List it here

Open an issue at [github.com/kasperjunge/agent-resources](https://github.com/kasperjunge/agent-resources/issues) to get your skill added to this directory.

See [Creating Skills](creating.md) for a full guide on writing effective skills.
