"""CLI tests for agr onboard command."""

import json

from agr.config import AgrConfig
from tests.cli.assertions import assert_cli


# All interactive onboard tests need _AGR_FORCE_TTY=1 to bypass the isatty check
# since subprocess input= pipes stdin rather than using a real TTY.
_TTY_ENV = {"_AGR_FORCE_TTY": "1"}


class TestAgrOnboard:
    """Tests for agr onboard command."""

    def test_onboard_non_tty_fails_with_hint(self, agr, cli_project):
        """agr onboard with piped stdin fails with helpful error."""
        # Don't set _AGR_FORCE_TTY — this tests the real TTY check
        result = agr("onboard", input="")

        assert_cli(result).failed().stdout_contains("interactive terminal")
        assert_cli(result).stdout_contains("agr init")

    def test_onboard_creates_config(self, agr, cli_project):
        """agr onboard with input creates agr.toml."""
        # Select tool 1 (claude), accept all defaults, confirm
        result = agr("onboard", input="1\n\ny\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        assert (cli_project / "agr.toml").exists()

    def test_onboard_detects_and_presents_tools(self, agr, cli_project):
        """agr onboard shows detected tools in output."""
        (cli_project / ".claude").mkdir()

        result = agr("onboard", input="1\n\ny\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        assert_cli(result).stdout_contains("detected")

    def test_onboard_accepts_defaults_on_enter(self, agr, cli_project):
        """agr onboard with Enter at each step uses detected defaults."""
        (cli_project / ".claude").mkdir()

        # Enter (accept default tools), Enter (accept default skills), y (confirm)
        result = agr("onboard", input="\n\ny\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert "claude" in config.tools

    def test_onboard_custom_tool_selection(self, agr, cli_project):
        """agr onboard allows selecting specific tools by number."""
        # Select tools 1,3 (claude, codex), no skills, pick default, confirm
        result = agr("onboard", input="1,3\n\nclaude\ny\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert "claude" in config.tools
        assert "codex" in config.tools

    def test_onboard_discovers_skills(self, agr, cli_project, cli_skill):
        """agr onboard discovers skills and shows them."""
        # Select tools (1=claude), select skills (1=test-skill), confirm
        result = agr("onboard", input="1\n1\ny\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        assert_cli(result).stdout_contains("test-skill")
        config = AgrConfig.load(cli_project / "agr.toml")
        paths = {dep.path for dep in config.dependencies if dep.path}
        assert any("test-skill" in p for p in paths)

    def test_onboard_skips_skills_if_none(self, agr, cli_project):
        """agr onboard skips skill step when none found."""
        result = agr("onboard", input="1\n\ny\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        assert_cli(result).stdout_contains("No skills found")

    def test_onboard_default_tool_multi(self, agr, cli_project):
        """agr onboard prompts for default tool when multiple selected."""
        # Select tools 1,3 (claude, codex), no skills, pick default tool, confirm
        result = agr("onboard", input="1,3\n\nclaude\ny\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.default_tool == "claude"

    def test_onboard_default_tool_single_skipped(self, agr, cli_project):
        """agr onboard skips default tool step when only one tool selected."""
        # Select tool 1 only, no skills, confirm
        result = agr("onboard", input="1\n\ny\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        config = AgrConfig.load(cli_project / "agr.toml")
        assert config.default_tool is None

    def test_onboard_cancel_writes_nothing(self, agr, cli_project):
        """agr onboard with 'n' at confirm writes no config."""
        # Select tool 1, no skills (no prompt), decline confirm
        result = agr("onboard", input="1\nn\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        assert not (cli_project / "agr.toml").exists()

    def test_onboard_existing_config_as_defaults(self, agr, cli_project, cli_config):
        """agr onboard with existing config shows configured tools."""
        cli_config('tools = ["claude", "codex"]\ndependencies = []\n')

        # Accept defaults, confirm
        result = agr("onboard", input="\n\nclaude\ny\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        assert_cli(result).stdout_contains("configured")

    def test_onboard_no_migrate_skips_migration(self, agr, cli_project):
        """agr onboard --no-migrate keeps skills in tool folder."""
        # Place a skill in .claude/skills/
        tool_skill = cli_project / ".claude" / "skills" / "my-skill"
        tool_skill.mkdir(parents=True)
        (tool_skill / "SKILL.md").write_text("---\nname: my-skill\n---\n# My Skill\n")

        # Select claude (1), select skill (1), confirm
        result = agr("onboard", "--no-migrate", input="1\n1\ny\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        # Migration prompt should not appear
        assert_cli(result).stdout_not_contains("Move them to ./skills/")
        # Skill should still be in original location
        assert tool_skill.exists()
        assert not (cli_project / "skills" / "my-skill").exists()

    def test_onboard_skips_remote_skills_in_migration(self, agr, cli_project):
        """agr onboard does not offer to migrate remote-installed skills."""
        # Place a remote-installed skill in .claude/skills/ with remote metadata
        tool_skill = cli_project / ".claude" / "skills" / "remote-skill"
        tool_skill.mkdir(parents=True)
        (tool_skill / "SKILL.md").write_text(
            "---\nname: remote-skill\n---\n# Remote Skill\n"
        )
        (tool_skill / ".agr.json").write_text(
            json.dumps(
                {
                    "id": "remote:github:someone/repo/remote-skill",
                    "tool": "claude",
                    "installed_name": "remote-skill",
                    "type": "remote",
                    "handle": "someone/repo/remote-skill",
                    "source": "github",
                }
            )
        )

        # Select claude (1), select skill (1), confirm
        result = agr("onboard", input="1\n1\ny\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        # Migration prompt should NOT appear for remote-only skills
        assert_cli(result).stdout_not_contains("Move them to ./skills/")
        # Skill should stay in .claude/skills/
        assert tool_skill.exists()
        assert not (cli_project / "skills" / "remote-skill").exists()

    def test_onboard_migrates_local_but_not_remote(self, agr, cli_project):
        """agr onboard migrates local tool-folder skills but skips remote ones."""
        # Remote skill in .claude/skills/
        remote_skill = cli_project / ".claude" / "skills" / "remote-skill"
        remote_skill.mkdir(parents=True)
        (remote_skill / "SKILL.md").write_text(
            "---\nname: remote-skill\n---\n# Remote\n"
        )
        (remote_skill / ".agr.json").write_text(
            json.dumps({"type": "remote", "id": "remote:github:x/y/remote-skill"})
        )

        # Local (user-authored) skill in .claude/skills/ — no .agr.json
        local_skill = cli_project / ".claude" / "skills" / "local-skill"
        local_skill.mkdir(parents=True)
        (local_skill / "SKILL.md").write_text("---\nname: local-skill\n---\n# Local\n")

        # Select claude (1), select both skills, accept migration, confirm
        result = agr("onboard", input="1\n1,2\ny\ny\n", env=_TTY_ENV)

        assert_cli(result).succeeded()
        # Migration prompt should appear (for the local skill)
        assert_cli(result).stdout_contains("Move them to ./skills/")
        # Local skill should be migrated
        assert (cli_project / "skills" / "local-skill").exists()
        # Remote skill should NOT be migrated
        assert not (cli_project / "skills" / "remote-skill").exists()
        assert remote_skill.exists()
