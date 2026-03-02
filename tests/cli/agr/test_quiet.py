"""CLI tests for --quiet flag across commands."""

from tests.cli.assertions import assert_cli


class TestQuietFlag:
    """Tests for --quiet / -q global flag."""

    def test_init_quiet_suppresses_output(self, agr, cli_project):
        """agr -q init produces no stdout."""
        result = agr("-q", "init")

        assert_cli(result).succeeded().stdout_is_empty()
        assert (cli_project / "agr.toml").exists()

    def test_add_quiet_suppresses_output(self, agr, cli_skill):
        """agr -q add produces no stdout on success."""
        result = agr("-q", "add", "./skills/test-skill")

        assert_cli(result).succeeded().stdout_is_empty()

    def test_sync_quiet_suppresses_output(self, agr, cli_project, cli_config):
        """agr -q sync produces no stdout."""
        cli_config("dependencies = []")

        result = agr("-q", "sync")

        assert_cli(result).succeeded().stdout_is_empty()

    def test_remove_quiet_suppresses_output(self, agr, cli_project, cli_skill):
        """agr -q remove produces no stdout on success."""
        # First add the skill normally
        agr("add", "./skills/test-skill")

        result = agr("-q", "remove", "./skills/test-skill")

        assert_cli(result).succeeded().stdout_is_empty()

    def test_list_quiet_suppresses_output(self, agr, cli_project, cli_config):
        """agr -q list produces no stdout."""
        cli_config("dependencies = []")

        result = agr("-q", "list")

        assert_cli(result).succeeded().stdout_is_empty()

    def test_quiet_error_still_fails(self, agr, cli_project, cli_config):
        """agr -q add ./nonexistent exits with non-zero code even in quiet mode."""
        cli_config("dependencies = []")

        result = agr("-q", "add", "./nonexistent")

        assert_cli(result).failed().stdout_is_empty()
