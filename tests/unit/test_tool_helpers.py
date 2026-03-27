"""Unit tests for agr.commands._tool_helpers module."""

import pytest

from agr.commands._tool_helpers import (
    ToolAddResult,
    ToolRemoveResult,
    add_tools_to_config,
    ensure_valid_default_tool,
    normalize_and_validate_tool_names,
    normalize_tool_names,
    remove_tools_from_config,
    validate_tool_names,
)
from agr.config import AgrConfig


class TestNormalizeToolNames:
    """Tests for normalize_tool_names()."""

    def test_lowercase_and_strip(self):
        assert normalize_tool_names(["  Claude ", "CURSOR"]) == ["claude", "cursor"]

    def test_empty_strings_removed(self):
        assert normalize_tool_names(["claude", "", "  "]) == ["claude"]

    def test_empty_list(self):
        assert normalize_tool_names([]) == []

    def test_already_normalized(self):
        assert normalize_tool_names(["claude", "cursor"]) == ["claude", "cursor"]


class TestValidateToolNames:
    """Tests for validate_tool_names()."""

    def test_valid_names_pass(self):
        validate_tool_names(["claude", "cursor", "codex"])

    def test_single_invalid_name_exits(self):
        with pytest.raises(SystemExit):
            validate_tool_names(["not-a-tool"])

    def test_mixed_valid_invalid_exits(self):
        with pytest.raises(SystemExit):
            validate_tool_names(["claude", "not-a-tool"])

    def test_empty_list_passes(self):
        validate_tool_names([])


class TestNormalizeAndValidateToolNames:
    """Tests for normalize_and_validate_tool_names()."""

    def test_normalizes_and_validates(self):
        result = normalize_and_validate_tool_names(["  Claude ", "CURSOR"])
        assert result == ["claude", "cursor"]

    def test_deduplicates(self):
        result = normalize_and_validate_tool_names(["claude", "Claude", "CLAUDE"])
        assert result == ["claude"]

    def test_empty_exits_by_default(self):
        with pytest.raises(SystemExit):
            normalize_and_validate_tool_names([])

    def test_empty_allowed_when_allow_empty(self):
        result = normalize_and_validate_tool_names([], allow_empty=True)
        assert result == []

    def test_only_whitespace_exits(self):
        with pytest.raises(SystemExit):
            normalize_and_validate_tool_names(["  ", ""])

    def test_invalid_tool_exits(self):
        with pytest.raises(SystemExit):
            normalize_and_validate_tool_names(["fake-tool"])

    def test_preserves_order(self):
        result = normalize_and_validate_tool_names(["cursor", "claude", "codex"])
        assert result == ["cursor", "claude", "codex"]


class TestAddToolsToConfig:
    """Tests for add_tools_to_config()."""

    def test_adds_new_tools(self):
        config = AgrConfig(tools=["claude"])
        result = add_tools_to_config(config, ["cursor", "codex"])

        assert result == ToolAddResult(added=["cursor", "codex"], skipped=[])
        assert config.tools == ["claude", "cursor", "codex"]

    def test_skips_existing_tools(self):
        config = AgrConfig(tools=["claude", "cursor"])
        result = add_tools_to_config(config, ["claude", "codex"])

        assert result == ToolAddResult(added=["codex"], skipped=["claude"])
        assert config.tools == ["claude", "cursor", "codex"]

    def test_all_already_configured(self):
        config = AgrConfig(tools=["claude", "cursor"])
        result = add_tools_to_config(config, ["claude", "cursor"])

        assert result == ToolAddResult(added=[], skipped=["claude", "cursor"])
        assert config.tools == ["claude", "cursor"]

    def test_empty_names_list(self):
        config = AgrConfig(tools=["claude"])
        result = add_tools_to_config(config, [])

        assert result == ToolAddResult(added=[], skipped=[])
        assert config.tools == ["claude"]


class TestRemoveToolsFromConfig:
    """Tests for remove_tools_from_config()."""

    def test_removes_configured_tool(self, tmp_path):
        config = AgrConfig(tools=["claude", "cursor"])
        result = remove_tools_from_config(config, ["cursor"], tmp_path)

        assert result.removed == ["cursor"]
        assert result.not_configured == []
        assert config.tools == ["claude"]

    def test_reports_not_configured(self, tmp_path):
        config = AgrConfig(tools=["claude", "cursor"])
        result = remove_tools_from_config(config, ["codex"], tmp_path)

        assert result.removed == []
        assert result.not_configured == ["codex"]
        assert config.tools == ["claude", "cursor"]

    def test_mixed_configured_and_not(self, tmp_path):
        config = AgrConfig(tools=["claude", "cursor"])
        result = remove_tools_from_config(config, ["cursor", "codex"], tmp_path)

        assert result.removed == ["cursor"]
        assert result.not_configured == ["codex"]

    def test_cannot_remove_all_tools(self, tmp_path):
        config = AgrConfig(tools=["claude"])
        with pytest.raises(SystemExit):
            remove_tools_from_config(config, ["claude"], tmp_path)

    def test_none_repo_root_skips_deletion(self):
        config = AgrConfig(tools=["claude", "cursor"])
        result = remove_tools_from_config(config, ["cursor"], None)

        assert result.removed == ["cursor"]
        assert config.tools == ["claude"]


class TestEnsureValidDefaultTool:
    """Tests for ensure_valid_default_tool()."""

    def test_keeps_valid_default(self):
        config = AgrConfig(tools=["claude", "cursor"])
        config.default_tool = "cursor"
        ensure_valid_default_tool(config, "cursor")

        assert config.default_tool == "cursor"

    def test_replaces_removed_default_with_first_tool(self, capsys):
        config = AgrConfig(tools=["claude"])
        config.default_tool = None
        ensure_valid_default_tool(config, "cursor")

        assert config.default_tool == "claude"
        captured = capsys.readouterr()
        assert "Default tool updated" in captured.out

    def test_noop_when_previous_default_was_none(self):
        config = AgrConfig(tools=["claude"])
        config.default_tool = None
        ensure_valid_default_tool(config, None)

        assert config.default_tool is None

    def test_unsets_when_no_tools_remain(self, capsys):
        config = AgrConfig(tools=[])
        config.default_tool = None
        ensure_valid_default_tool(config, "claude")

        assert config.default_tool is None
        captured = capsys.readouterr()
        assert "Default tool unset" in captured.out

    def test_noop_when_default_still_in_tools(self):
        config = AgrConfig(tools=["claude", "cursor"])
        config.default_tool = "claude"
        ensure_valid_default_tool(config, "claude")

        assert config.default_tool == "claude"


class TestToolAddResult:
    """Tests for ToolAddResult dataclass."""

    def test_equality(self):
        a = ToolAddResult(added=["claude"], skipped=["cursor"])
        b = ToolAddResult(added=["claude"], skipped=["cursor"])
        assert a == b

    def test_inequality(self):
        a = ToolAddResult(added=["claude"], skipped=[])
        b = ToolAddResult(added=[], skipped=["claude"])
        assert a != b


class TestToolRemoveResult:
    """Tests for ToolRemoveResult dataclass."""

    def test_equality(self):
        a = ToolRemoveResult(removed=["cursor"], not_configured=["codex"])
        b = ToolRemoveResult(removed=["cursor"], not_configured=["codex"])
        assert a == b

    def test_inequality(self):
        a = ToolRemoveResult(removed=["cursor"], not_configured=[])
        b = ToolRemoveResult(removed=[], not_configured=["cursor"])
        assert a != b
