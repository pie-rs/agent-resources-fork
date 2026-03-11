# Contributing guide for AI agents

## Quick reference

### Run tests
```bash
uv run pytest                    # all tests
uv run pytest tests/test_foo.py  # specific file
uv run pytest -k "test_name"    # specific test
```

### Lint and format
```bash
uv run ruff check .    # lint
uv run ruff format .   # format
uv run ty check        # type check
```

### Test the CLI
```bash
uv run agr --help
uv run agrx --help
```

## Where to find things

| I want to... | Look at... |
|---|---|
| Add a new CLI command | `agr/commands/` — create a module, wire it in `agr/main.py` |
| Change how skills are installed | `agr/fetcher.py` |
| Change handle parsing | `agr/handle.py` |
| Change config file format | `agr/config.py` |
| Add a new AI tool | `agr/tool.py` — add a `ToolConfig` instance and register in `TOOLS` dict |
| Change git behavior | `agr/git.py` |
| Change skill discovery | `agr/skill.py` |
| Change metadata format | `agr/metadata.py` |
| Change agrx behavior | `agrx/main.py` |
| Add SDK functionality | `agr/sdk/` |
| Update MkDocs site | `docs/docs/` |

## Conventions

### Code style
- Python 3.12+, type hints on all public functions
- Docstrings on all public functions and classes (Google style)
- Ruff for linting and formatting
- No bare `except` — catch specific exceptions
- Module-level docstring on every file

### Testing conventions
- Every new feature needs tests
- Use `tmp_path` for filesystem operations
- Use `monkeypatch` for mocking
- Test files mirror source layout: `agr/fetcher.py` → `tests/test_fetcher.py`

### agr and agrx sync
These two CLIs must stay functionally aligned. Changes to shared behavior (handle parsing, git operations, skill discovery) apply to both. The `agrx` runner reuses the core `agr/` library.

### Skills directory
Save all skills in `skills/` (not `.claude/skills/` which is gitignored).

## Common patterns in the codebase

### Context managers for temp resources
`downloaded_repo()` and `_rollback_on_failure()` use `@contextmanager` to ensure cleanup:

```python
with downloaded_repo(source, owner, repo) as repo_dir:
    # repo_dir is cleaned up automatically
    skill = find_skill_in_repo(repo_dir, name)
```

### Handle → install path resolution
The path where a skill is installed depends on the tool:
- Flat tools: `_resolve_skill_destination()` in `fetcher.py`
- Nested tools: `handle.to_skill_path(tool)` in `handle.py`

### Config discovery
`find_config()` walks up from cwd to git root looking for `agr.toml`. Global config lives at `~/.agr/agr.toml`.

### Source resolution
`SourceResolver.ordered(explicit_source)` returns sources in priority order. Default source comes first, others follow. If an explicit source is given, only that source is tried.

### Multi-tool install with rollback
`fetch_and_install_to_tools()` downloads once, installs to all tools. If any tool fails, all already-installed copies are removed via `_rollback_on_failure()`.
