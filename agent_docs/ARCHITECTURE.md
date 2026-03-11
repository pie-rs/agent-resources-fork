# Architecture

## Overview

Agent Resources (`agr`) is a package manager for AI agent skills. It installs skill files (markdown prompts with optional supporting files) from GitHub repositories into the configuration directories of various AI coding tools (Claude Code, Cursor, Codex, etc.).

## Project structure

```
agr/                  # Core library
  main.py             # CLI entry point (Typer app)
  handle.py           # Handle parsing (ParsedHandle)
  config.py           # agr.toml management (AgrConfig, Dependency)
  tool.py             # Tool definitions (ToolConfig: claude, cursor, codex, etc.)
  source.py           # Git source resolution (SourceConfig, SourceResolver)
  fetcher.py          # Install/uninstall orchestration
  git.py              # Git clone, sparse checkout, token injection
  skill.py            # SKILL.md discovery and validation
  metadata.py         # .agr.json read/write in installed skill dirs
  detect.py           # Auto-detect tools present in a repo
  instructions.py     # Sync CLAUDE.md/AGENTS.md/GEMINI.md
  console.py          # Rich console output with --quiet
  exceptions.py       # AgrError hierarchy
  commands/            # CLI command implementations
    add.py             # agr add
    remove.py          # agr remove
    sync.py            # agr sync
    list.py            # agr list
    init.py            # agr init
    onboard.py         # agr onboard
    config_cmd.py      # agr config {show,path,edit,get,set,unset,add,remove}
    tools.py           # agr config tools (deprecated sub-commands)
    migrations.py      # Legacy skill migration utilities
    _tool_helpers.py   # Shared helpers for tool-related commands
  sdk/                 # Programmatic Python API
    __init__.py        # Public exports: Skill, cache, list_skills, skill_info
    skill.py           # Skill class for loading and running skills
    cache.py           # GitHub API caching (skill listings, metadata)
    hub.py             # Hub operations (search, list from GitHub API)
    types.py           # SkillInfo type definition

agrx/                 # Ephemeral skill runner CLI
  main.py             # agrx CLI: download, run, discard

tests/                # Pytest test suite
docs/                 # MkDocs site source
agent_docs/           # This directory — documentation for AI agents
```

## Key types

### ParsedHandle (`handle.py`)

Represents a parsed skill reference. Two forms:

- **Remote**: `ParsedHandle(username="user", repo="repo", name="skill")` — from `user/repo/skill` or `user/skill` (repo defaults to `"skills"`)
- **Local**: `ParsedHandle(is_local=True, name="my-skill", local_path=Path("./my-skill"))` — from `./my-skill`

Key methods:
- `to_toml_handle()` → string for agr.toml (`"user/skill"` or `"./path"`)
- `to_installed_name()` → flat directory name with `--` separator (`"user--skill"`)
- `to_skill_path(tool)` → installation path relative to skills dir (flat or nested depending on tool)
- `get_github_repo()` → `(owner, repo_name)` tuple for git operations

### ToolConfig (`tool.py`)

Frozen dataclass defining how a tool stores skills. Key fields:

- `name` — tool identifier (e.g., `"claude"`, `"cursor"`)
- `config_dir` — project-level config directory (e.g., `".claude"`)
- `skills_subdir` — subdirectory for skills (always `"skills"`)
- `supports_nested` — `True` for Cursor (nested `user/repo/skill/` dirs), `False` for others (flat naming)
- `get_skills_dir(repo_root)` → `repo_root / config_dir / skills_subdir`
- CLI fields (`cli_command`, `cli_prompt_flag`, etc.) — used by agrx to invoke the tool

Six tools defined: `CLAUDE`, `CURSOR`, `CODEX`, `OPENCODE`, `COPILOT`, `ANTIGRAVITY`.

### AgrConfig (`config.py`)

Loaded from `agr.toml`. Contains:

- `dependencies: list[Dependency]` — skills to install
- `tools: list[str]` — target tools (default: `["claude"]`)
- `sources: list[SourceConfig]` — git sources (default: GitHub)
- `default_source`, `default_tool`, `sync_instructions`, `canonical_instructions`

Methods: `load(path)`, `save(path)`, `add_dependency()`, `remove_dependency()`, `get_tools()`, `get_source_resolver()`

### Dependency (`config.py`)

A single entry in the dependencies array:

- `handle` — remote reference (e.g., `"user/skill"`)
- `path` — local path (e.g., `"./my-skill"`)
- `type` — always `"skill"` currently
- `source` — optional explicit source name
- `to_parsed_handle()` → converts to `ParsedHandle`

### SourceConfig (`source.py`)

A git source with URL template: `name`, `type` (always `"git"`), `url` (e.g., `"https://github.com/{owner}/{repo}.git"`).

## Core workflows

### Install (`agr add user/skill`)

```
parse_handle("user/skill")
  → ParsedHandle(username="user", name="skill")

AgrConfig.load("agr.toml")
  → config with tools=["claude"], sources=[github]

For each tool in config.tools:
  fetch_and_install(handle, repo_root, tool)
    → _locate_remote_skill(handle, resolver)
      → iter_repo_candidates(handle.repo)  # ["skills", "agent-resources"]
        → For each repo candidate + source:
          → downloaded_repo(source, owner, repo_name)
            → git clone --depth 1 --filter=blob:none
          → prepare_repo_for_skill(repo_dir, skill_name)
            → git ls-tree → find SKILL.md → sparse checkout
    → install_skill_from_repo(repo_dir, skill_name, handle, skills_dir, tool)
      → _resolve_skill_destination()  # where to put it
      → _copy_skill_to_destination()  # shutil.copytree + metadata

config.add_dependency(Dependency(handle="user/skill", type="skill"))
config.save()
```

### Uninstall (`agr remove user/skill`)

```
parse_handle → find existing skill dir via metadata matching → shutil.rmtree → clean empty parents
config.remove_dependency() → config.save()
```

### Sync (`agr sync`)

Iterates `config.dependencies`, calls `fetch_and_install()` for each one that isn't already installed (checked via `is_skill_installed()`).

### Local install (`agr add ./my-skill`)

Copies the local directory to the tool's skills dir. Validates `SKILL.md` exists. Checks for name conflicts with other local skills.

## Naming conventions

### Flat tools (Claude, Codex, OpenCode, Copilot, Antigravity)

Skills are installed as top-level directories in the skills folder:
- Default: `<skills-dir>/<skill-name>/`
- On name collision: `<skills-dir>/<user>--<repo>--<skill>/`

### Nested tools (Cursor)

Skills preserve the full handle path:
- Remote: `<skills-dir>/<user>/<repo>/<skill>/`
- Local: `<skills-dir>/local/<skill>/`

## Metadata (`.agr.json`)

Each installed skill directory contains `.agr.json` with:

```json
{
  "id": "remote:github:user/skill",
  "tool": "claude",
  "installed_name": "skill",
  "type": "remote",
  "handle": "user/skill",
  "source": "github",
  "content_hash": "sha256:..."
}
```

Used for: matching skills to handles during uninstall/sync, detecting name conflicts, content change detection.

## Error handling

All errors inherit from `AgrError` (`exceptions.py`):

- `RepoNotFoundError` — remote repo doesn't exist
- `AuthenticationError` — git auth failure (private repo, no token)
- `SkillNotFoundError` — skill directory not found in repo
- `ConfigError` — invalid agr.toml
- `InvalidHandleError` — unparseable handle string
- `CacheError` — SDK cache failures
- `RateLimitError` — GitHub API rate limit

Multi-tool installs use `_rollback_on_failure()` context manager to clean up partial installs.

## Testing

Tests live in `tests/`. Key patterns:

- `tmp_path` fixtures for filesystem tests
- `monkeypatch` for mocking git operations and subprocess calls
- Tests are organized by module: `test_fetcher.py`, `test_config.py`, `test_skill.py`, etc.
- Run with `uv run pytest`

## SDK (`agr/sdk/`)

Programmatic API for using agr from Python code:

```python
from agr import Skill, cache, list_skills, skill_info

# Load a skill from GitHub (cached locally)
skill = Skill.from_git("user/skill")
print(skill.prompt)   # Contents of SKILL.md
print(skill.files)    # List of files in the skill directory

# Load a local skill
skill = Skill.from_local("./my-skill")

# Discover skills in a repo
skills = list_skills("anthropics/skills")
info = skill_info("anthropics/skills/code-review")

# Cache management
cache.info()          # {"skills_count": N, "size_bytes": N, ...}
cache.clear()         # Clear all cached skills
cache.clear("user/*") # Clear by pattern
```

Skills are cached in `~/.cache/agr/skills/` keyed by `source/owner/repo/skill/revision`. The cache uses file locking for concurrent safety and atomic writes via temp dir + rename.
