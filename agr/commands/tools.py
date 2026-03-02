"""agr tool-configuration command implementations."""

import shutil
from pathlib import Path

from agr.config import AgrConfig, find_config, find_repo_root
from agr.console import get_console
from agr.exceptions import AgrError
from agr.fetcher import fetch_and_install_to_tools, is_skill_installed
from agr.handle import ParsedHandle, parse_handle
from agr.tool import DEFAULT_TOOL_NAMES, TOOLS


def _normalize_tool_names(tool_names: list[str]) -> list[str]:
    """Normalize user-provided tool names."""
    return [name.strip().lower() for name in tool_names if name.strip()]


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    """Remove duplicates while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _validate_tool_names(tool_names: list[str]) -> None:
    """Validate tool names against TOOLS registry."""
    console = get_console()
    invalid = [name for name in tool_names if name not in TOOLS]
    if invalid:
        available = ", ".join(TOOLS.keys())
        console.print(f"[red]Error:[/red] Unknown tool(s): {', '.join(invalid)}")
        console.print(f"[dim]Available tools: {available}[/dim]")
        raise SystemExit(1)


def _load_required_config() -> AgrConfig:
    """Load agr.toml or exit with a user-facing error."""
    console = get_console()
    config_path = find_config()
    if config_path is None:
        console.print("[red]Error:[/red] No agr.toml found.")
        console.print("[dim]Run 'agr init' first to create one.[/dim]")
        raise SystemExit(1)
    return AgrConfig.load(config_path)


def _sync_dependencies_to_tools(config: AgrConfig, tool_names: list[str]) -> int:
    """Install existing dependencies into newly added tools.

    Returns:
        Number of dependencies that failed to sync.
    """
    console = get_console()
    if not tool_names or not config.dependencies:
        return 0

    repo_root = find_repo_root()
    if repo_root is None:
        console.print(
            "[yellow]Warning:[/yellow] Not in a git repository, "
            "cannot sync dependencies."
        )
        return 0

    console.print()
    console.print(
        f"[dim]Syncing {len(config.dependencies)} dependencies to new tools...[/dim]"
    )

    new_tools = [TOOLS[name] for name in tool_names]
    resolver = config.get_source_resolver()
    sync_errors = 0

    for dep in config.dependencies:
        try:
            if dep.is_local:
                ref = dep.path or ""
                source_name = None
            else:
                ref = dep.handle or ""
                source_name = dep.source or config.default_source

            if dep.is_local:
                path = Path(ref)
                handle = ParsedHandle(is_local=True, name=path.name, local_path=path)
            else:
                handle = parse_handle(ref, prefer_local=False)

            tools_needing_install = [
                tool
                for tool in new_tools
                if not is_skill_installed(handle, repo_root, tool, source_name)
            ]

            if not tools_needing_install:
                continue

            fetch_and_install_to_tools(
                handle,
                repo_root,
                tools_needing_install,
                overwrite=False,
                resolver=resolver,
                source=source_name,
            )

            tool_list = ", ".join(t.name for t in tools_needing_install)
            console.print(f"[green]Installed:[/green] {dep.identifier} ({tool_list})")

        except AgrError as e:
            console.print(f"[red]Error:[/red] {dep.identifier}: {e}")
            sync_errors += 1
        except Exception as e:
            console.print(f"[red]Error:[/red] {dep.identifier}: {e}")
            sync_errors += 1

    return sync_errors


def _delete_tool_skills(tool_name: str, repo_root: Path | None) -> bool:
    """Delete all skills for a configured tool."""
    console = get_console()
    if repo_root is None:
        return True

    tool_config = TOOLS[tool_name]
    skills_dir = tool_config.get_skills_dir(repo_root)
    if not skills_dir.exists():
        return True

    skill_count = sum(1 for entry in skills_dir.iterdir() if entry.is_dir())
    try:
        shutil.rmtree(skills_dir)
        console.print(
            f"[dim]Deleted {skill_count} skills from {skills_dir.relative_to(repo_root)}/[/dim]"
        )
    except OSError as e:
        console.print(f"[red]Error deleting skills:[/red] {e}")
        console.print(f"[dim]Tool '{tool_name}' not removed from config[/dim]")
        return False

    return True


def _ensure_valid_default_tool(
    config: AgrConfig, previous_default_tool: str | None
) -> None:
    """Keep default_tool valid after tool list updates."""
    console = get_console()
    if config.default_tool and config.default_tool in config.tools:
        return
    if previous_default_tool is None:
        return

    replacement = config.tools[0] if config.tools else None
    config.default_tool = replacement
    if replacement:
        console.print(
            "[yellow]Default tool updated:[/yellow] "
            f"{previous_default_tool} -> {replacement}"
        )
    else:
        console.print("[yellow]Default tool unset:[/yellow] no tools configured")


def run_tools_list() -> None:
    """List configured tools and available tool names."""
    console = get_console()
    config_path = find_config()

    if config_path:
        config = AgrConfig.load(config_path)
        configured = config.tools
    else:
        configured = list(DEFAULT_TOOL_NAMES)
        console.print("[dim]No agr.toml found, showing defaults[/dim]")
        console.print()

    available = [name for name in TOOLS.keys() if name not in configured]

    console.print("[bold]Configured tools:[/bold]")
    if configured:
        for tool_name in configured:
            console.print(f"  - {tool_name}")
    else:
        console.print("  [dim](none)[/dim]")

    if available:
        console.print()
        console.print(f"[dim]Available tools:[/dim] {', '.join(available)}")


def run_tools_add(tool_names: list[str]) -> None:
    """Add tools and sync existing dependencies to newly added tools."""
    console = get_console()
    names = _dedupe_preserve_order(_normalize_tool_names(tool_names))
    _validate_tool_names(names)

    config = _load_required_config()

    added: list[str] = []
    skipped: list[str] = []
    for name in names:
        if name in config.tools:
            skipped.append(name)
        else:
            config.tools.append(name)
            added.append(name)

    for name in added:
        console.print(f"[green]Added:[/green] {name}")
    for name in skipped:
        console.print(f"[dim]Already configured:[/dim] {name}")

    sync_errors = _sync_dependencies_to_tools(config, added)
    config.save()

    if sync_errors:
        console.print(
            f"[yellow]Warning:[/yellow] {sync_errors} dependency sync(s) failed"
        )
        raise SystemExit(1)


def run_tools_set(tool_names: list[str]) -> None:
    """Replace configured tools with the provided list."""
    console = get_console()
    names = _dedupe_preserve_order(_normalize_tool_names(tool_names))
    if not names:
        console.print("[red]Error:[/red] Cannot set empty tools list.")
        console.print("[dim]At least one tool must be configured.[/dim]")
        raise SystemExit(1)

    _validate_tool_names(names)
    config = _load_required_config()

    previous_tools = list(config.tools)
    previous_default_tool = config.default_tool
    added = [name for name in names if name not in previous_tools]
    removed = [name for name in previous_tools if name not in names]

    config.tools = names
    _ensure_valid_default_tool(config, previous_default_tool)

    if added:
        console.print(f"[green]Added:[/green] {', '.join(added)}")
    if removed:
        console.print(f"[yellow]Removed from config:[/yellow] {', '.join(removed)}")
    if not added and not removed and previous_tools == names:
        console.print("[dim]Tools already configured.[/dim]")
    elif not added and not removed:
        console.print("[green]Updated:[/green] Tool order changed")

    sync_errors = _sync_dependencies_to_tools(config, added)
    config.save()

    if sync_errors:
        console.print(
            f"[yellow]Warning:[/yellow] {sync_errors} dependency sync(s) failed"
        )
        raise SystemExit(1)


def run_tools_remove(tool_names: list[str]) -> None:
    """Remove tools from configuration and delete their installed skills."""
    console = get_console()
    names = _dedupe_preserve_order(_normalize_tool_names(tool_names))
    _validate_tool_names(names)

    config = _load_required_config()
    previous_default_tool = config.default_tool

    remaining = [tool for tool in config.tools if tool not in names]
    if not remaining:
        console.print("[red]Error:[/red] Cannot remove all tools.")
        console.print("[dim]At least one tool must be configured.[/dim]")
        raise SystemExit(1)

    repo_root = find_repo_root()
    removed: list[str] = []
    not_configured: list[str] = []

    for name in names:
        if name not in config.tools:
            not_configured.append(name)
            continue

        console.print(f"[yellow]Removing:[/yellow] {name}")
        if not _delete_tool_skills(name, repo_root):
            continue

        config.tools.remove(name)
        removed.append(name)

    _ensure_valid_default_tool(config, previous_default_tool)
    config.save()

    for name in removed:
        console.print(f"[green]Removed:[/green] {name}")
    for name in not_configured:
        console.print(f"[dim]Not configured:[/dim] {name}")


def run_default_tool_set(tool_name: str) -> None:
    """Set default_tool in agr.toml."""
    console = get_console()
    normalized = _normalize_tool_names([tool_name])
    if not normalized:
        console.print("[red]Error:[/red] Tool name is required.")
        raise SystemExit(1)

    name = normalized[0]
    _validate_tool_names([name])
    config = _load_required_config()

    if name not in config.tools:
        console.print(
            f"[red]Error:[/red] Tool '{name}' is not configured. "
            f"Add it first with 'agr config tools add {name}'."
        )
        raise SystemExit(1)

    if config.default_tool == name:
        console.print(f"[dim]Default tool already set:[/dim] {name}")
        return

    config.default_tool = name
    config.save()
    console.print(f"[green]Default tool set:[/green] {name}")


def run_default_tool_unset() -> None:
    """Unset default_tool in agr.toml."""
    console = get_console()
    config = _load_required_config()
    if config.default_tool is None:
        console.print("[dim]Default tool is already unset.[/dim]")
        return

    previous = config.default_tool
    config.default_tool = None
    config.save()
    console.print(f"[green]Default tool unset:[/green] {previous}")
