"""Shared console factory supporting --quiet flag."""

from rich.console import Console

_quiet = False


def set_quiet(value: bool) -> None:
    """Set global quiet mode."""
    global _quiet
    _quiet = value


def get_console() -> Console:
    """Get a Console instance respecting the global quiet setting."""
    return Console(quiet=_quiet)


def print_error(message: str) -> None:
    """Print a styled error message to the console."""
    get_console().print(f"[red]Error:[/red] {message}")
