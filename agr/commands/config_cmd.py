"""Unified agr config command implementations."""

import os
import shlex
import subprocess
from pathlib import Path

from agr.config import (
    AgrConfig,
    find_repo_root,
    get_global_config_path,
    require_config,
    validate_canonical_instructions,
)
from agr.commands._tool_helpers import (
    add_tools_to_config,
    ensure_valid_default_tool,
    exit_if_sync_errors,
    normalize_and_validate_tool_names,
    print_tool_add_result,
    print_tool_remove_result,
    remove_tools_from_config,
    sync_dependencies_to_tools,
)
from agr.console import error_exit, get_console
from agr.exceptions import ConfigError
from agr.source import DEFAULT_SOURCE_NAME, SourceConfig
from agr.tool import DEFAULT_TOOL_NAMES

VALID_KEYS = {
    "tools",
    "default_tool",
    "default_source",
    "sync_instructions",
    "canonical_instructions",
    "sources",
}

SCALAR_KEYS = {
    "default_tool",
    "default_source",
    "sync_instructions",
    "canonical_instructions",
}
LIST_KEYS = {"tools", "sources"}


def _require_config_path(global_scope: bool) -> Path:
    """Locate the config file path, exiting with a user-facing error if missing."""
    if not global_scope:
        return require_config()

    config_path = get_global_config_path()
    if not config_path.exists():
        error_exit(
            f"No global config found at {config_path}",
            hint="Run 'agr init' or create it manually.",
        )
    return config_path


def _load_config(global_scope: bool) -> tuple[AgrConfig, Path]:
    """Load config for local or global scope."""
    config_path = _require_config_path(global_scope)
    return AgrConfig.load(config_path), config_path


def _validate_key(key: str) -> None:
    """Validate key is in VALID_KEYS, exit with error listing valid keys."""
    if key not in VALID_KEYS:
        valid = ", ".join(sorted(VALID_KEYS))
        error_exit(f"Unknown config key '{key}'", hint=f"Valid keys: {valid}")


def _require_single_source_name(values: list[str]) -> str:
    """Validate that exactly one source name was provided and return it."""
    if not values:
        error_exit("Source name is required.")
    if len(values) > 1:
        error_exit("Only one source name allowed at a time.")
    return values[0]


def run_config_show(global_scope: bool) -> None:
    """Print formatted view of effective config."""
    console = get_console()
    config, config_path = _load_config(global_scope)

    console.print(f"[bold]Config:[/bold] {config_path}")
    console.print()
    console.print(f"  tools             = {', '.join(config.tools)}")
    console.print(f"  default_tool      = {config.default_tool or '(not set)'}")
    console.print(f"  default_source    = {config.default_source}")

    if config.sync_instructions is not None:
        console.print(f"  sync_instructions = {str(config.sync_instructions).lower()}")
    else:
        console.print("  sync_instructions = (not set)")

    console.print(
        f"  canonical_instructions = {config.canonical_instructions or '(not set)'}"
    )

    console.print()
    console.print("[bold]Sources:[/bold]")
    for src in config.sources:
        default_marker = " (default)" if src.name == config.default_source else ""
        console.print(f"  - {src.name} [{src.type}] {src.url}{default_marker}")


def run_config_path(global_scope: bool) -> None:
    """Print resolved agr.toml path."""
    print(_require_config_path(global_scope))


def run_config_edit(global_scope: bool) -> None:
    """Open agr.toml in $EDITOR."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        error_exit("Neither $VISUAL nor $EDITOR is set.")

    path = _require_config_path(global_scope)

    result = subprocess.run([*shlex.split(editor), str(path)])
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def run_config_get(key: str, global_scope: bool) -> None:
    """Print a config value."""
    _validate_key(key)
    config, _ = _load_config(global_scope)

    if key == "tools":
        print(" ".join(config.tools))
    elif key == "sources":
        for src in config.sources:
            print(f"{src.name} {src.type} {src.url}")
    elif key == "default_tool":
        print(config.default_tool or "(not set)")
    elif key == "default_source":
        print(config.default_source)
    elif key == "sync_instructions":
        if config.sync_instructions is not None:
            print(str(config.sync_instructions).lower())
        else:
            print("(not set)")
    elif key == "canonical_instructions":
        print(config.canonical_instructions or "(not set)")
    else:
        raise AssertionError(f"Unhandled key: {key}")


def run_config_set(key: str, values: list[str], global_scope: bool) -> None:
    """Write a scalar value or replace a list."""
    console = get_console()
    _validate_key(key)
    config, _ = _load_config(global_scope)

    if key == "sources":
        error_exit(
            "Cannot set sources directly. Use "
            "'agr config add sources' and "
            "'agr config remove sources'."
        )

    if key == "tools":
        names = normalize_and_validate_tool_names(values)
        previous_default = config.default_tool
        previous_tools = list(config.tools)
        config.tools = names
        ensure_valid_default_tool(config, previous_default)
        added = [n for n in names if n not in previous_tools]
        if not global_scope:
            sync_errors = sync_dependencies_to_tools(config, added)
            exit_if_sync_errors(sync_errors)
        config.save()
        console.print(f"[green]Set:[/green] tools = {', '.join(names)}")
        return

    # Scalar keys expect exactly one value
    if len(values) != 1:
        error_exit(f"'{key}' expects exactly one value.")

    value = values[0]

    if key == "default_tool":
        names = normalize_and_validate_tool_names([value])
        name = names[0]
        if name not in config.tools:
            error_exit(
                f"Tool '{name}' is not in configured tools. "
                f"Add it first with 'agr config add tools {name}'."
            )
        config.default_tool = name
        config.save()
        console.print(f"[green]Set:[/green] default_tool = {name}")

    elif key == "default_source":
        source_names = [s.name for s in config.sources]
        if value not in source_names:
            error_exit(
                f"Source '{value}' not found in sources list.",
                hint=f"Available sources: {', '.join(source_names)}",
            )
        config.default_source = value
        config.save()
        console.print(f"[green]Set:[/green] default_source = {value}")

    elif key == "sync_instructions":
        if value.lower() not in ("true", "false"):
            error_exit("sync_instructions must be 'true' or 'false'.")
        config.sync_instructions = value.lower() == "true"
        config.save()
        console.print(f"[green]Set:[/green] sync_instructions = {value.lower()}")

    elif key == "canonical_instructions":
        try:
            validate_canonical_instructions(value)
        except ConfigError as exc:
            error_exit(str(exc))
        config.canonical_instructions = value
        config.save()
        console.print(f"[green]Set:[/green] canonical_instructions = {value}")

    else:
        raise AssertionError(f"Unhandled key: {key}")


def run_config_unset(key: str, global_scope: bool) -> None:
    """Clear a config value to default/None."""
    console = get_console()
    _validate_key(key)
    config, _ = _load_config(global_scope)

    if key == "sources":
        error_exit("Cannot unset sources. Use 'agr config remove sources <name>'.")

    if key == "tools":
        previous_default = config.default_tool
        config.tools = list(DEFAULT_TOOL_NAMES)
        ensure_valid_default_tool(config, previous_default)
        config.save()
        console.print(f"[green]Reset:[/green] tools = {', '.join(DEFAULT_TOOL_NAMES)}")
        return

    if key == "default_source":
        config.default_source = DEFAULT_SOURCE_NAME
        config.save()
        console.print(f"[green]Reset:[/green] default_source = {DEFAULT_SOURCE_NAME}")
        return

    # Nullable scalar keys: default_tool, sync_instructions, canonical_instructions
    assert key in ("default_tool", "sync_instructions", "canonical_instructions"), (
        f"Unhandled key: {key}"
    )
    current = getattr(config, key)
    if current is None:
        console.print(f"[dim]{key} is already unset.[/dim]")
        return
    setattr(config, key, None)
    config.save()
    console.print(f"[green]Unset:[/green] {key}")


def run_config_add(
    key: str,
    values: list[str],
    source_type: str | None,
    source_url: str | None,
    global_scope: bool,
) -> None:
    """Append to a list config value."""
    console = get_console()
    _validate_key(key)
    config, _ = _load_config(global_scope)

    if key in SCALAR_KEYS:
        error_exit(f"'{key}' is a scalar. Use 'agr config set {key} <value>'.")

    # Reject --type/--url on non-sources keys
    if key != "sources" and (source_type is not None or source_url is not None):
        error_exit("--type and --url are only valid for 'sources'.")

    if key == "tools":
        names = normalize_and_validate_tool_names(values)
        result = add_tools_to_config(config, names)

        if not global_scope:
            sync_errors = sync_dependencies_to_tools(config, result.added)
            exit_if_sync_errors(sync_errors)
        if result.added:
            config.save()

        print_tool_add_result(result)

    elif key == "sources":
        name = _require_single_source_name(values)

        if source_type is None:
            source_type = "git"
        if source_type != "git":
            error_exit(
                f"Unsupported source type '{source_type}'. Only 'git' is supported."
            )
        if source_url is None:
            error_exit("--url is required when adding a source.")

        existing_names = {s.name for s in config.sources}
        if name in existing_names:
            error_exit(f"Source '{name}' already exists.")

        config.sources.append(SourceConfig(name=name, type=source_type, url=source_url))
        config.save()
        console.print(
            f"[green]Added source:[/green] {name} [{source_type}] {source_url}"
        )


def run_config_remove(key: str, values: list[str], global_scope: bool) -> None:
    """Remove from a list config value."""
    console = get_console()
    _validate_key(key)
    config, _ = _load_config(global_scope)

    if key in SCALAR_KEYS:
        error_exit(f"'{key}' is a scalar. Use 'agr config unset {key}'.")

    if key == "tools":
        names = normalize_and_validate_tool_names(values)
        repo_root = None if global_scope else find_repo_root()

        result = remove_tools_from_config(config, names, repo_root)
        config.save()
        print_tool_remove_result(result)

    elif key == "sources":
        name = _require_single_source_name(values)

        if name == config.default_source:
            error_exit(
                f"Cannot remove default source '{name}'. Change default_source first."
            )

        original_len = len(config.sources)
        config.sources = [s for s in config.sources if s.name != name]
        if len(config.sources) == original_len:
            error_exit(f"Source '{name}' not found.")

        config.save()
        console.print(f"[green]Removed source:[/green] {name}")
