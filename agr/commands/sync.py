"""agr sync command implementation."""

import shutil
from dataclasses import dataclass
from pathlib import Path

from agr.config import AgrConfig, find_config, get_global_config_path, require_repo_root
from agr.console import get_console
from agr.exceptions import AgrError
from agr.fetcher import (
    downloaded_repo,
    fetch_and_install_to_tools,
    install_skill_from_repo_to_tools,
    is_skill_installed,
    prepare_repo_for_skills,
)
from agr.handle import (
    INSTALLED_NAME_SEPARATOR,
    LEGACY_SEPARATOR,
    ParsedHandle,
    parse_handle,
)
from agr.instructions import (
    canonical_instruction_file,
    sync_instruction_files,
)
from agr.metadata import (
    build_handle_id,
    compute_content_hash,
    read_skill_metadata,
    write_skill_metadata,
)
from agr.source import DEFAULT_SOURCE_NAME
from agr.skill import SKILL_MARKER, is_valid_skill_dir, update_skill_md_name
from agr.tool import ToolConfig


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


def _migrate_skills_directory(
    old_skills_dir: Path,
    new_skills_dir: Path,
    *,
    cleanup_parent: bool = False,
) -> None:
    """Migrate skills from one directory to another.

    Moves skill subdirectories from old_skills_dir to new_skills_dir,
    skipping any that already exist at the target. Cleans up the old
    directory if empty after migration.

    Args:
        old_skills_dir: The old skills directory to migrate from.
        new_skills_dir: The new skills directory to migrate to.
        cleanup_parent: If True, also remove the parent of old_skills_dir
            when it becomes empty (e.g., removing .codex/ after .codex/skills/).
    """
    console = get_console()

    if not old_skills_dir.exists():
        return

    old_label = old_skills_dir.name
    old_parent_label = old_skills_dir.parent.name
    old_rel = f"{old_parent_label}/{old_label}"
    new_label = new_skills_dir.name
    new_parent_label = new_skills_dir.parent.name
    new_rel = f"{new_parent_label}/{new_label}"

    new_skills_dir.mkdir(parents=True, exist_ok=True)

    for skill_dir in old_skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        target = new_skills_dir / skill_dir.name
        if target.exists():
            console.print(
                f"[yellow]Cannot migrate:[/yellow] {old_rel}/{skill_dir.name}"
            )
            console.print(
                f"  [dim]Target {new_rel}/{skill_dir.name} already exists[/dim]"
            )
            continue

        try:
            shutil.move(str(skill_dir), target)
            console.print(
                f"[blue]Migrated:[/blue] {old_rel}/{skill_dir.name} -> {new_rel}/{skill_dir.name}"
            )
        except OSError as e:
            console.print(f"[red]Failed to migrate:[/red] {old_rel}/{skill_dir.name}")
            console.print(f"  [dim]{e}[/dim]")

    # Warn about non-directory files left behind
    if old_skills_dir.exists():
        leftover = [f for f in old_skills_dir.iterdir() if not f.is_dir()]
        if leftover:
            console.print(
                f"[yellow]Note:[/yellow] {len(leftover)} non-skill file(s) remain in {old_rel}/"
            )

    # Clean up empty old directory
    if old_skills_dir.exists() and not any(old_skills_dir.iterdir()):
        old_skills_dir.rmdir()

    # Optionally clean up empty parent directory
    if cleanup_parent:
        parent = old_skills_dir.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()


def migrate_codex_skills_directory(
    old_skills_dir: Path, new_skills_dir: Path, tool: ToolConfig
) -> None:
    """Migrate skills from .codex/skills/ to .agents/skills/ for Codex.

    Codex moved its skills directory from .codex/ to .agents/. This migrates
    any existing skills installed under the old path.

    Args:
        old_skills_dir: The old skills directory (e.g., repo_root / ".codex" / "skills").
        new_skills_dir: The new skills directory (e.g., repo_root / ".agents" / "skills").
        tool: Tool configuration (only runs for codex).
    """
    if tool.name != "codex":
        return
    _migrate_skills_directory(old_skills_dir, new_skills_dir, cleanup_parent=True)


def migrate_opencode_skills_directory(
    old_skills_dir: Path, new_skills_dir: Path, tool: ToolConfig
) -> None:
    """Migrate skills from .opencode/skill/ to .opencode/skills/ for OpenCode.

    OpenCode updated its skills directory from skill/ to skills/. This migrates
    any existing skills installed under the old path.

    Args:
        old_skills_dir: The old skills directory (e.g., repo_root / ".opencode" / "skill").
        new_skills_dir: The new skills directory (e.g., repo_root / ".opencode" / "skills").
        tool: Tool configuration (only runs for opencode).
    """
    if tool.name != "opencode":
        return
    _migrate_skills_directory(old_skills_dir, new_skills_dir, cleanup_parent=False)


def run_tool_migrations(
    tools: list[ToolConfig],
    repo_root: Path | None,
    global_install: bool = False,
) -> None:
    """Run all tool-specific directory migrations.

    Handles Codex (.codex/ -> .agents/) and OpenCode (.opencode/skill/ ->
    .opencode/skills/) migrations for each tool.

    Args:
        tools: List of tool configurations to migrate.
        repo_root: Repository root for local installs, or None.
        global_install: If True, use home directory paths for global installs.
    """
    base = Path.home() if global_install else repo_root
    if base is None:
        return

    for tool in tools:
        migrate_codex_skills_directory(
            base / ".codex" / "skills",
            base / ".agents" / "skills",
            tool,
        )
        # Use global_config_dir for global installs (e.g., .config/opencode)
        opencode_dir = (
            tool.global_config_dir
            if global_install and tool.global_config_dir
            else tool.config_dir
        )
        migrate_opencode_skills_directory(
            base / opencode_dir / "skill",
            base / opencode_dir / "skills",
            tool,
        )


def _migrate_legacy_directories(skills_dir: Path, tool: ToolConfig) -> None:
    """Migrate colon-based directory names to the new separator format.

    This ensures backward compatibility with skills installed before
    the Windows-compatible naming scheme was introduced.

    Only applies to flat tools (Claude), not nested tools (Cursor).

    Args:
        skills_dir: The skills directory to scan for legacy directories.
        tool: Tool configuration (migration only for non-nested tools).
    """
    console = get_console()
    # Only migrate for flat tools
    if tool.supports_nested:
        return

    if not skills_dir.exists():
        return

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        if LEGACY_SEPARATOR not in skill_dir.name:
            continue
        # Verify it's a skill (has SKILL.md)
        if not (skill_dir / SKILL_MARKER).exists():
            continue

        # Convert legacy separator to new separator
        new_name = skill_dir.name.replace(LEGACY_SEPARATOR, INSTALLED_NAME_SEPARATOR)
        new_path = skills_dir / new_name

        if new_path.exists():
            console.print(f"[yellow]Cannot migrate:[/yellow] {skill_dir.name}")
            console.print(f"  [dim]Target {new_name} already exists[/dim]")
            continue

        try:
            skill_dir.rename(new_path)
            console.print(f"[blue]Migrated:[/blue] {skill_dir.name} -> {new_name}")
        except OSError as e:
            console.print(f"[red]Failed to migrate:[/red] {skill_dir.name}")
            console.print(f"  [dim]{e}[/dim]")


def _migrate_flat_installed_names(
    skills_dir: Path,
    tool: ToolConfig,
    config: AgrConfig,
    repo_root: Path,
) -> None:
    """Migrate flat skill names to the plain <skill> format when safe.

    Only applies to flat tools. Uses agr.toml dependencies to resolve
    handle identities and writes metadata for accurate future matching.
    """
    console = get_console()
    # TODO(decide): consider best-effort migration for installs not in agr.toml.
    # This is ambiguous for local skills because the original path is unknown,
    # and for remotes because multiple handles can share the same skill name.
    if tool.supports_nested:
        return

    if not skills_dir.exists():
        return

    # Build handles from config dependencies
    handles_by_name: dict[str, list[tuple[ParsedHandle, str | None]]] = {}
    for dep in config.dependencies:
        ref = dep.path or dep.handle or ""
        if not ref:
            continue
        try:
            if dep.is_local:
                path = Path(ref)
                handle = ParsedHandle(is_local=True, name=path.name, local_path=path)
                source_name = None
            else:
                handle = parse_handle(ref, prefer_local=False)
                source_name = dep.source or config.default_source
        except Exception:
            continue
        handles_by_name.setdefault(handle.name, []).append((handle, source_name))

    for skill_name, handles in handles_by_name.items():
        name_dir = skills_dir / skill_name
        name_dir_is_skill = is_valid_skill_dir(name_dir)

        # If a name dir exists, try to match metadata to a handle
        matched_handle: tuple[ParsedHandle, str | None] | None = None
        if name_dir_is_skill:
            meta = read_skill_metadata(name_dir)
            if meta:
                for handle, source_name in handles:
                    handle_id = build_handle_id(handle, repo_root, source_name)
                    legacy_id = (
                        build_handle_id(handle, repo_root)
                        if source_name == DEFAULT_SOURCE_NAME
                        else None
                    )
                    if meta.get("id") in {handle_id, legacy_id}:
                        matched_handle = (handle, source_name)
                        break

        # If there is only one handle for this name, ensure name dir metadata
        if len(handles) == 1:
            handle, source_name = handles[0]
            handle_id = build_handle_id(handle, repo_root, source_name)
            if name_dir_is_skill:
                meta = read_skill_metadata(name_dir)
                if not meta or meta.get("id") != handle_id:
                    update_skill_md_name(name_dir, name_dir.name)
                    write_skill_metadata(
                        name_dir,
                        handle,
                        repo_root,
                        tool.name,
                        name_dir.name,
                        source_name,
                        compute_content_hash(name_dir),
                    )
                continue

            # No name dir: try to migrate from full flat name
            full_dir = skills_dir / handle.to_installed_name()
            if is_valid_skill_dir(full_dir):
                if not name_dir.exists():
                    try:
                        full_dir.rename(name_dir)
                        update_skill_md_name(name_dir, name_dir.name)
                        write_skill_metadata(
                            name_dir,
                            handle,
                            repo_root,
                            tool.name,
                            name_dir.name,
                            source_name,
                            compute_content_hash(name_dir),
                        )
                        console.print(
                            f"[blue]Migrated:[/blue] {full_dir.name} -> {name_dir.name}"
                        )
                    except OSError as e:
                        console.print(f"[red]Failed to migrate:[/red] {full_dir.name}")
                        console.print(f"  [dim]{e}[/dim]")
                else:
                    # Name exists but isn't a skill dir; skip rename
                    pass
            continue

        # Multiple handles with same name: avoid renaming to plain name
        if matched_handle:
            update_skill_md_name(name_dir, name_dir.name)
            write_skill_metadata(
                name_dir,
                matched_handle[0],
                repo_root,
                tool.name,
                name_dir.name,
                matched_handle[1],
                compute_content_hash(name_dir),
            )

        # Ensure metadata on full-name dirs for all handles
        for handle, source_name in handles:
            full_dir = skills_dir / handle.to_installed_name()
            if is_valid_skill_dir(full_dir):
                update_skill_md_name(full_dir, full_dir.name)
                write_skill_metadata(
                    full_dir,
                    handle,
                    repo_root,
                    tool.name,
                    full_dir.name,
                    source_name,
                    compute_content_hash(full_dir),
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
    skills_dirs = {tool.name: tool.get_global_skills_dir() for tool in tools}

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
        ref = dep.path or dep.handle or ""
        try:
            if dep.is_local:
                path = Path(ref)
                handle = ParsedHandle(is_local=True, name=path.name, local_path=path)
                source_name = None
            else:
                handle = parse_handle(ref, prefer_local=False)
                source_name = dep.source or config.default_source

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
        except (FileExistsError, AgrError) as e:
            console.print(f"[red]Error:[/red] {identifier}")
            console.print(f"  [dim]{e}[/dim]")
            errors += 1
        except Exception as e:
            console.print(f"[red]Error:[/red] {identifier}")
            console.print(f"  [dim]Unexpected: {e}[/dim]")
            errors += 1

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
        _migrate_legacy_directories(skills_dir, tool)
        _migrate_flat_installed_names(skills_dir, tool, config, repo_root)

    if not config.dependencies:
        console.print("[yellow]No dependencies in agr.toml.[/yellow] Nothing to sync.")
        return

    resolver = config.get_source_resolver()

    # Track results per dependency (not per tool)
    results: list[tuple[str, str | None] | None] = [None for _ in config.dependencies]
    pending_local: list[SyncEntry] = []
    pending_remote: list[SyncEntry] = []

    def _skill_not_found_message(name: str) -> str:
        return (
            f"Skill '{name}' not found in repository.\n"
            f"No directory named '{name}' containing SKILL.md was found.\n"
            f"Hint: Create a skill at 'skills/{name}/SKILL.md' or '{name}/SKILL.md'"
        )

    for index, dep in enumerate(config.dependencies):
        identifier = dep.identifier
        try:
            # Parse handle
            ref = dep.path or dep.handle or ""
            if dep.is_local:
                path = Path(ref)
                handle = ParsedHandle(is_local=True, name=path.name, local_path=path)
            else:
                handle = parse_handle(ref, prefer_local=False)
            source_name = None if dep.is_local else dep.source or config.default_source

            tools_needing_install = _filter_tools_needing_install(
                handle, repo_root, tools, source_name
            )

            if not tools_needing_install:
                results[index] = ("up-to-date", None)
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
        except AgrError as e:
            results[index] = ("error", str(e))
        except Exception as e:
            results[index] = ("error", f"Unexpected: {e}")

    def _sync_entries(entries: list[SyncEntry]) -> None:
        """Fetch and install a list of sync entries individually."""
        for entry in entries:
            handle = entry.handle
            tools_needing_install = _filter_tools_needing_install(
                handle, repo_root, tools, entry.source_name
            )
            if not tools_needing_install:
                results[entry.index] = ("up-to-date", None)
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
                results[entry.index] = ("installed", None)
            except (FileExistsError, AgrError) as e:
                results[entry.index] = ("error", str(e))
            except Exception as e:
                results[entry.index] = ("error", f"Unexpected: {e}")

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
                        results[entry.index] = ("up-to-date", None)
                        continue
                    skill_source = skill_sources.get(handle.name)
                    if skill_source is None:
                        results[entry.index] = (
                            "error",
                            _skill_not_found_message(handle.name),
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
                        results[entry.index] = ("installed", None)
                    except (FileExistsError, AgrError) as e:
                        results[entry.index] = ("error", str(e))
                    except Exception as e:
                        results[entry.index] = ("error", f"Unexpected: {e}")
        except AgrError as e:
            for entry in entries:
                results[entry.index] = ("error", str(e))
        except Exception as e:
            for entry in entries:
                results[entry.index] = ("error", f"Unexpected: {e}")

    # Print results
    installed = 0
    up_to_date = 0
    errors = 0

    for index, dep in enumerate(config.dependencies):
        identifier = dep.identifier
        status, error = results[index] or ("error", "Unexpected error")
        if status == "installed":
            console.print(f"[green]Installed:[/green] {identifier}")
            installed += 1
        elif status == "up-to-date":
            console.print(f"[dim]Up to date:[/dim] {identifier}")
            up_to_date += 1
        else:
            console.print(f"[red]Error:[/red] {identifier}")
            if error:
                console.print(f"  [dim]{error}[/dim]")
            errors += 1

    # Summary
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
