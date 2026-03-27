"""Unit tests for the git module's pure helper functions."""

import os
from unittest.mock import patch

from agr.git import get_github_token
from agr.git import _is_github_source as is_github_source
from agr.git import _partial_clone_unsupported as partial_clone_unsupported
from agr.git import _apply_github_token as apply_github_token
from agr.source import SourceConfig


class TestGetGithubToken:
    """Tests for get_github_token()."""

    def test_returns_none_when_no_env_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            assert get_github_token() is None

    def test_prefers_github_token_over_gh_token(self):
        with patch.dict(
            os.environ, {"GITHUB_TOKEN": "gh-token", "GH_TOKEN": "cli-token"}
        ):
            assert get_github_token() == "gh-token"

    def test_falls_back_to_gh_token(self):
        env = {"GH_TOKEN": "cli-token"}
        with patch.dict(os.environ, env, clear=True):
            assert get_github_token() == "cli-token"

    def test_ignores_empty_github_token(self):
        env = {"GITHUB_TOKEN": "", "GH_TOKEN": "cli-token"}
        with patch.dict(os.environ, env, clear=True):
            assert get_github_token() == "cli-token"

    def test_ignores_whitespace_only_github_token(self):
        env = {"GITHUB_TOKEN": "   ", "GH_TOKEN": "cli-token"}
        with patch.dict(os.environ, env, clear=True):
            assert get_github_token() == "cli-token"

    def test_strips_whitespace_from_token(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "  my-token  "}, clear=True):
            assert get_github_token() == "my-token"

    def test_returns_none_when_both_empty(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=True):
            assert get_github_token() is None


class TestIsGithubSource:
    """Tests for _is_github_source()."""

    def test_github_https_url(self):
        source = SourceConfig(name="default", type="github", url="https://github.com")
        assert is_github_source(source) is True

    def test_github_url_case_insensitive(self):
        source = SourceConfig(name="default", type="github", url="https://GitHub.COM")
        assert is_github_source(source) is True

    def test_non_github_url(self):
        source = SourceConfig(name="gitlab", type="gitlab", url="https://gitlab.com")
        assert is_github_source(source) is False

    def test_github_enterprise_url(self):
        source = SourceConfig(name="ghe", type="github", url="https://github.com/enterprise")
        assert is_github_source(source) is True


class TestPartialCloneUnsupported:
    """Tests for _partial_clone_unsupported()."""

    def test_none_stderr(self):
        assert partial_clone_unsupported(None) is False

    def test_empty_stderr(self):
        assert partial_clone_unsupported("") is False

    def test_old_git_client(self):
        assert partial_clone_unsupported("error: unknown option `--filter'") is True

    def test_server_rejects_filter(self):
        assert partial_clone_unsupported("fatal: filtering is not supported") is True

    def test_alternate_server_phrasing(self):
        assert (
            partial_clone_unsupported("error: does not support filtering") is True
        )

    def test_rare_git_build(self):
        assert partial_clone_unsupported("filtering not recognized by server") is True

    def test_unrelated_error(self):
        assert partial_clone_unsupported("fatal: repository not found") is False

    def test_case_insensitive(self):
        assert partial_clone_unsupported("ERROR: Unknown Option `--filter'") is True


class TestApplyGithubToken:
    """Tests for _apply_github_token()."""

    def test_no_token_returns_original_url(self):
        url = "https://github.com/owner/repo.git"
        with patch.dict(os.environ, {}, clear=True):
            assert apply_github_token(url) == url

    def test_injects_token_into_github_url(self):
        url = "https://github.com/owner/repo.git"
        with patch.dict(os.environ, {"GITHUB_TOKEN": "my-token"}, clear=True):
            result = apply_github_token(url)
            assert "my-token" in result
            assert result.startswith("https://")
            assert "github.com" in result

    def test_non_https_url_unchanged(self):
        url = "git@github.com:owner/repo.git"
        with patch.dict(os.environ, {"GITHUB_TOKEN": "my-token"}, clear=True):
            assert apply_github_token(url) == url

    def test_non_github_url_unchanged(self):
        url = "https://gitlab.com/owner/repo.git"
        with patch.dict(os.environ, {"GITHUB_TOKEN": "my-token"}, clear=True):
            assert apply_github_token(url) == url

    def test_url_with_existing_auth_unchanged(self):
        url = "https://user@github.com/owner/repo.git"
        with patch.dict(os.environ, {"GITHUB_TOKEN": "my-token"}, clear=True):
            assert apply_github_token(url) == url

    def test_special_chars_in_token_are_encoded(self):
        url = "https://github.com/owner/repo.git"
        with patch.dict(os.environ, {"GITHUB_TOKEN": "tok/en@val"}, clear=True):
            result = apply_github_token(url)
            # '/' and '@' should be percent-encoded
            assert "tok%2Fen%40val" in result
