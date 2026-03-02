"""Unit tests for agr.detect module."""

from agr.detect import _TOOL_SIGNALS, detect_tools
from agr.tool import TOOLS


class TestToolSignalsRegistry:
    """Tests that _TOOL_SIGNALS stays in sync with TOOLS."""

    def test_tool_signals_keys_match_tools_keys(self):
        """_TOOL_SIGNALS must cover exactly the same tools as TOOLS."""
        assert set(_TOOL_SIGNALS.keys()) == set(TOOLS.keys())


class TestDetectTools:
    """Tests for detect_tools()."""

    def test_no_signals_returns_empty(self, tmp_path):
        """detect_tools returns [] when no signals are present."""
        assert detect_tools(tmp_path) == []

    def test_single_signal_detected(self, tmp_path):
        """detect_tools finds a tool when one signal exists."""
        (tmp_path / ".claude").mkdir()

        result = detect_tools(tmp_path)

        assert result == ["claude"]

    def test_multiple_tools_detected(self, tmp_path):
        """detect_tools finds multiple tools from their signals."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".cursor").mkdir()
        (tmp_path / ".codex").mkdir()

        result = detect_tools(tmp_path)

        assert "claude" in result
        assert "cursor" in result
        assert "codex" in result

    def test_file_signal_detected(self, tmp_path):
        """detect_tools detects tools from file signals (not just dirs)."""
        (tmp_path / "CLAUDE.md").write_text("# Instructions")

        result = detect_tools(tmp_path)

        assert "claude" in result

    def test_nested_signal_detected(self, tmp_path):
        """detect_tools detects tools from nested path signals."""
        (tmp_path / ".github" / "copilot").mkdir(parents=True)

        result = detect_tools(tmp_path)

        assert "copilot" in result
