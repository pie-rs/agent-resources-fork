"""Tool detection by checking multiple signals per tool."""

from pathlib import Path

from agr.tool import TOOLS

# Detection signals per tool: (tool_name, list of path patterns)
# Any matching path signals the tool is present.
_TOOL_SIGNALS: dict[str, list[str]] = {
    "claude": [".claude", "CLAUDE.md"],
    "cursor": [".cursor", ".cursorrules"],
    "codex": [".agents", ".codex"],
    "opencode": [".opencode"],
    "copilot": [".github/copilot", ".github/skills"],
    "antigravity": [".agent"],
}


def detect_tools(repo_root: Path) -> list[str]:
    """Detect tools by checking multiple signals per tool.

    Checks for config directories, instruction files, and other
    tool-specific markers. Any single signal is enough to detect a tool.

    Args:
        repo_root: Repository root path to check.

    Returns:
        List of detected tool names. Empty list if nothing detected.
    """
    detected: list[str] = []
    for tool_name in TOOLS:
        signals = _TOOL_SIGNALS.get(tool_name, [])
        for signal in signals:
            if (repo_root / signal).exists():
                detected.append(tool_name)
                break
    return detected
