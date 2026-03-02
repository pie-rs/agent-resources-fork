"""agr list command implementation."""

from pathlib import Path

from rich.table import Table

from agr.config import AgrConfig, find_config, find_repo_root, get_global_config_path
from agr.console import get_console
from agr.fetcher import is_skill_installed
from agr.handle import ParsedHandle, parse_handle
from agr.tool import ToolConfig


def _get_installation_status(
    handle: ParsedHandle,
    repo_root: Path | None,
    tools: list[ToolConfig],
    source: str | None = None,
    skills_dirs: dict[str, Path] | None = None,
) -> str:
    """Get installation status across all configured tools.

    Args:
        handle: Parsed handle for the skill
        repo_root: Repository root path
        tools: List of ToolConfig instances

    Returns:
        Formatted status string
    """
    installed_tools = [
        tool.name
        for tool in tools
        if is_skill_installed(
            handle,
            repo_root,
            tool,
            source,
            skills_dir=skills_dirs.get(tool.name) if skills_dirs is not None else None,
        )
    ]

    if len(installed_tools) == len(tools):
        return "[green]installed[/green]"
    elif installed_tools:
        return f"[yellow]partial ({', '.join(installed_tools)})[/yellow]"
    else:
        return "[yellow]not synced[/yellow]"


def run_list(global_install: bool = False) -> None:
    """Run the list command.

    Lists all dependencies from agr.toml with their sync status.
    """
    console = get_console()
    skills_dirs: dict[str, Path] | None = None
    if global_install:
        repo_root = None
        config_path = get_global_config_path()
        if not config_path.exists():
            console.print("[yellow]No global agr.toml found.[/yellow]")
            console.print("[dim]Run 'agr add -g <handle>' to create one.[/dim]")
            return
    else:
        # Find repo root
        repo_root = find_repo_root()
        if repo_root is None:
            console.print("[red]Error:[/red] Not in a git repository")
            raise SystemExit(1)

        # Find config
        config_path = find_config()
        if config_path is None:
            console.print("[yellow]No agr.toml found.[/yellow]")
            console.print("[dim]Run 'agr init' to create one.[/dim]")
            return

    config = AgrConfig.load(config_path)
    tools = config.get_tools()
    if global_install:
        skills_dirs = {tool.name: tool.get_global_skills_dir() for tool in tools}

    if not config.dependencies:
        console.print("[yellow]No dependencies in agr.toml.[/yellow]")
        console.print("[dim]Run 'agr add <handle>' to add skills.[/dim]")
        return

    # Build table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Skill", style="cyan")
    table.add_column("Type")
    table.add_column("Status")

    for dep in config.dependencies:
        identifier = dep.identifier

        # Determine display name and status
        if dep.is_local:
            display_name = dep.path or ""
            source = "local"
        else:
            display_name = dep.handle or ""
            source = "remote"

        # Check installation status
        try:
            if dep.is_local:
                path = Path(identifier)
                handle = ParsedHandle(is_local=True, name=path.name, local_path=path)
            else:
                handle = parse_handle(identifier, prefer_local=False)
            source_name = (
                None if dep.is_local else (dep.source or config.default_source)
            )
            status = _get_installation_status(
                handle, repo_root, tools, source_name, skills_dirs
            )
        except Exception:
            status = "[red]invalid[/red]"

        table.add_row(display_name, source, status)

    console.print(table)

    # Show config path
    console.print()
    console.print(f"[dim]Config: {config_path}[/dim]")
