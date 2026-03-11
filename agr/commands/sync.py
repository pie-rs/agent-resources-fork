"""agr sync command implementation."""

from dataclasses import dataclass
from pathlib import Path

from agr.commands.migrations import (
    migrate_flat_installed_names,
    migrate_legacy_directories,
    run_tool_migrations,
)
from agr.config import AgrConfig, find_config, get_global_config_path, require_repo_root
from agr.console import get_console
from agr.exceptions import INSTALL_ERROR_TYPES, format_install_error
from agr.fetcher import (
    downloaded_repo,
    fetch_and_install_to_tools,
    install_skill_from_repo_to_tools,
    is_skill_installed,
    prepare_repo_for_skills,
    skill_not_found_message,
)
from agr.handle import ParsedHandle
from agr.instructions import (
    canonical_instruction_file,
    sync_instruction_files,
)
from agr.tool import ToolConfig, build_global_skills_dirs


def _print_sync_summary(installed: int, up_to_date: int, errors: int) -> None:
    """Print sync summary and exit with error if any failures occurred."""
    console = get_console()
    console.print()
    parts = []
    if installed:
        parts.append(f"{installed} installed")
    if up_to_date:
        parts.append(f"{up_to_date} up to date")
    if errors:
        parts.append(f"{errors} failed")
    console.print(f"[bold]Summary:[/bold] {', '.join(parts)}")

    if errors:
        raise SystemExit(1)


def _filter_tools_needing_install(
    handle: ParsedHandle,
    repo_root: Path | None,
    tools: list[ToolConfig],
    source_name: str | None,
    skills_dirs: dict[str, Path] | None = None,
) -> list[ToolConfig]:
    """Return tools where the given skill is not yet installed."""
    return [
        tool
        for tool in tools
        if not is_skill_installed(
            handle,
            repo_root,
            tool,
            source_name,
            skills_dir=skills_dirs.get(tool.name) if skills_dirs else None,
        )
    ]


@dataclass
class SyncResult:
    """Result of syncing a single dependency."""

    status: str  # "pending", "up-to-date", "installed", "error"
    error: str | None = None


@dataclass
class SyncEntry:
    index: int
    identifier: str
    handle: ParsedHandle
    source_name: str | None


def _sync_instructions_if_configured(
    repo_root: Path, config: AgrConfig, tools: list[ToolConfig]
) -> None:
    console = get_console()
    if not config.sync_instructions:
        return
    if len(tools) < 2:
        return

    if config.canonical_instructions:
        canonical_file = config.canonical_instructions
    else:
        tool_name = config.default_tool or tools[0].name
        canonical_file = canonical_instruction_file(tool_name)

    # Canonical source must exist — otherwise there is nothing to sync from.
    if not (repo_root / canonical_file).exists():
        console.print(
            f"[yellow]Instruction sync skipped:[/yellow] {canonical_file} not found."
        )
        return

    # Build the set of target files from all configured tools (excluding canonical).
    target_files = sorted(
        {
            canonical_instruction_file(tool.name)
            for tool in tools
            if canonical_instruction_file(tool.name) != canonical_file
        }
    )

    if not target_files:
        return

    updated = sync_instruction_files(repo_root, canonical_file, target_files)
    if updated:
        updated_list = ", ".join(updated)
        console.print(
            f"[green]Synced instructions:[/green] {canonical_file} -> {updated_list}"
        )


def _run_global_sync() -> None:
    """Sync global dependencies from ~/.agr/agr.toml."""
    console = get_console()
    config_path = get_global_config_path()
    if not config_path.exists():
        console.print("[yellow]No global agr.toml found.[/yellow] Nothing to sync.")
        console.print("[dim]Run 'agr add -g <handle>' to create one.[/dim]")
        return

    config = AgrConfig.load(config_path)
    tools = config.get_tools()
    skills_dirs = build_global_skills_dirs(tools)

    run_tool_migrations(tools, repo_root=None, global_install=True)

    if not config.dependencies:
        console.print(
            "[yellow]No dependencies in global agr.toml.[/yellow] Nothing to sync."
        )
        return

    resolver = config.get_source_resolver()

    installed = 0
    up_to_date = 0
    errors = 0

    for dep in config.dependencies:
        identifier = dep.identifier
        try:
            handle = dep.to_parsed_handle()
            source_name = dep.resolve_source_name(config.default_source)

            tools_needing_install = _filter_tools_needing_install(
                handle, None, tools, source_name, skills_dirs
            )

            if not tools_needing_install:
                console.print(f"[dim]Up to date:[/dim] {identifier}")
                up_to_date += 1
                continue

            fetch_and_install_to_tools(
                handle,
                None,
                tools_needing_install,
                overwrite=False,
                resolver=resolver,
                source=source_name,
                skills_dirs=skills_dirs,
            )
            console.print(f"[green]Installed:[/green] {identifier}")
            installed += 1
        except INSTALL_ERROR_TYPES as e:
            console.print(f"[red]Error:[/red] {identifier}")
            console.print(f"  [dim]{format_install_error(e)}[/dim]")
            errors += 1

    _print_sync_summary(installed, up_to_date, errors)


def run_sync(global_install: bool = False) -> None:
    """Run the sync command.

    Installs all dependencies from agr.toml that aren't already installed.
    Also migrates any legacy colon-based directory names to the new
    Windows-compatible double-hyphen format (for flat tools only).
    """
    console = get_console()
    if global_install:
        _run_global_sync()
        return

    repo_root = require_repo_root()

    # Find config
    config_path = find_config()
    if config_path is None:
        console.print("[yellow]No agr.toml found.[/yellow] Nothing to sync.")
        return

    config = AgrConfig.load(config_path)

    # Get configured tools
    tools = config.get_tools()

    _sync_instructions_if_configured(repo_root, config, tools)

    # Migrate legacy directories
    run_tool_migrations(tools, repo_root)
    for tool in tools:
        skills_dir = tool.get_skills_dir(repo_root)
        migrate_legacy_directories(skills_dir, tool)
        migrate_flat_installed_names(skills_dir, tool, config, repo_root)

    if not config.dependencies:
        console.print("[yellow]No dependencies in agr.toml.[/yellow] Nothing to sync.")
        return

    resolver = config.get_source_resolver()

    # Track results per dependency (not per tool)
    results: list[SyncResult] = [SyncResult("pending") for _ in config.dependencies]
    pending_local: list[SyncEntry] = []
    pending_remote: list[SyncEntry] = []

    for index, dep in enumerate(config.dependencies):
        identifier = dep.identifier
        try:
            handle = dep.to_parsed_handle()
            source_name = dep.resolve_source_name(config.default_source)

            tools_needing_install = _filter_tools_needing_install(
                handle, repo_root, tools, source_name
            )

            if not tools_needing_install:
                results[index] = SyncResult("up-to-date")
                continue

            entry = SyncEntry(
                index=index,
                identifier=identifier,
                handle=handle,
                source_name=source_name,
            )
            if dep.is_local:
                pending_local.append(entry)
            else:
                pending_remote.append(entry)
        except INSTALL_ERROR_TYPES as e:
            results[index] = SyncResult("error", format_install_error(e))

    def _sync_entries(entries: list[SyncEntry]) -> None:
        """Fetch and install a list of sync entries individually."""
        for entry in entries:
            handle = entry.handle
            tools_needing_install = _filter_tools_needing_install(
                handle, repo_root, tools, entry.source_name
            )
            if not tools_needing_install:
                results[entry.index] = SyncResult("up-to-date")
                continue
            try:
                fetch_and_install_to_tools(
                    handle,
                    repo_root,
                    tools_needing_install,
                    overwrite=False,
                    resolver=resolver,
                    source=entry.source_name,
                )
                results[entry.index] = SyncResult("installed")
            except INSTALL_ERROR_TYPES as e:
                results[entry.index] = SyncResult("error", format_install_error(e))

    # Local installs (no download)
    _sync_entries(pending_local)

    pending_remote_default = [e for e in pending_remote if e.handle.repo is None]
    pending_remote_specific = [e for e in pending_remote if e.handle.repo is not None]

    _sync_entries(pending_remote_default)

    # Remote installs grouped by repo/source (download once per repo)
    grouped: dict[tuple[str, str, str], list[SyncEntry]] = {}
    for entry in pending_remote_specific:
        handle = entry.handle
        source_name = entry.source_name or config.default_source
        owner, repo_name = handle.get_github_repo()
        key = (source_name, owner, repo_name)
        grouped.setdefault(key, []).append(entry)

    for (source_name, owner, repo_name), entries in grouped.items():
        try:
            source_config = resolver.get(source_name)
            with downloaded_repo(source_config, owner, repo_name) as repo_dir:
                skill_names = [entry.handle.name for entry in entries]
                skill_sources = prepare_repo_for_skills(repo_dir, skill_names)
                for entry in entries:
                    handle = entry.handle
                    tools_needing_install = _filter_tools_needing_install(
                        handle, repo_root, tools, entry.source_name
                    )
                    if not tools_needing_install:
                        results[entry.index] = SyncResult("up-to-date")
                        continue
                    skill_source = skill_sources.get(handle.name)
                    if skill_source is None:
                        results[entry.index] = SyncResult(
                            "error",
                            skill_not_found_message(handle.name),
                        )
                        continue
                    try:
                        install_skill_from_repo_to_tools(
                            repo_dir,
                            handle.name,
                            handle,
                            tools_needing_install,
                            repo_root,
                            overwrite=False,
                            install_source=source_name,
                            skill_source=skill_source,
                        )
                        results[entry.index] = SyncResult("installed")
                    except INSTALL_ERROR_TYPES as e:
                        results[entry.index] = SyncResult(
                            "error", format_install_error(e)
                        )
        except INSTALL_ERROR_TYPES as e:
            for entry in entries:
                results[entry.index] = SyncResult("error", format_install_error(e))

    # Print results
    installed = 0
    up_to_date = 0
    errors = 0

    for index, dep in enumerate(config.dependencies):
        identifier = dep.identifier
        result = results[index]
        if result.status == "installed":
            console.print(f"[green]Installed:[/green] {identifier}")
            installed += 1
        elif result.status == "up-to-date":
            console.print(f"[dim]Up to date:[/dim] {identifier}")
            up_to_date += 1
        else:
            console.print(f"[red]Error:[/red] {identifier}")
            if result.error:
                console.print(f"  [dim]{result.error}[/dim]")
            errors += 1

    _print_sync_summary(installed, up_to_date, errors)
