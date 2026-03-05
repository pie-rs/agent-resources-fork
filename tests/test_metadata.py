"""Tests for agr.metadata module."""

import re
from pathlib import Path

from agr.handle import ParsedHandle
from agr.metadata import (
    METADATA_FILENAME,
    compute_content_hash,
    read_skill_metadata,
    write_skill_metadata,
)


class TestComputeContentHash:
    """Tests for compute_content_hash function."""

    def test_deterministic(self, tmp_path: Path):
        """Same directory produces the same hash."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Hello")
        (skill_dir / "helper.py").write_text("print('hi')")

        hash1 = compute_content_hash(skill_dir)
        hash2 = compute_content_hash(skill_dir)
        assert hash1 == hash2

    def test_format(self, tmp_path: Path):
        """Hash matches sha256:<64 hex chars> format."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Hello")

        result = compute_content_hash(skill_dir)
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", result)

    def test_excludes_agr_json(self, tmp_path: Path):
        """Adding .agr.json does not change the hash."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Hello")

        hash_before = compute_content_hash(skill_dir)
        (skill_dir / METADATA_FILENAME).write_text('{"id": "test"}')
        hash_after = compute_content_hash(skill_dir)

        assert hash_before == hash_after

    def test_detects_rename(self, tmp_path: Path):
        """Renaming a file changes the hash."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Hello")
        (skill_dir / "a.py").write_text("code")

        hash1 = compute_content_hash(skill_dir)
        (skill_dir / "a.py").rename(skill_dir / "b.py")
        hash2 = compute_content_hash(skill_dir)

        assert hash1 != hash2

    def test_detects_content_change(self, tmp_path: Path):
        """Changing file contents changes the hash."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Hello")

        hash1 = compute_content_hash(skill_dir)
        (skill_dir / "SKILL.md").write_text("# Changed")
        hash2 = compute_content_hash(skill_dir)

        assert hash1 != hash2

    def test_handles_binary(self, tmp_path: Path):
        """Binary files are hashed correctly."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Hello")
        (skill_dir / "data.bin").write_bytes(b"\x00\x01\x02\xff")

        result = compute_content_hash(skill_dir)
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", result)

    def test_sorts_by_posix_path(self, tmp_path: Path):
        """Hash is the same regardless of file creation order."""
        # Create dir1 with files in one order
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "b.txt").write_text("B")
        (dir1 / "a.txt").write_text("A")

        # Create dir2 with files in reverse order
        dir2 = tmp_path / "dir2"
        dir2.mkdir()
        (dir2 / "a.txt").write_text("A")
        (dir2 / "b.txt").write_text("B")

        assert compute_content_hash(dir1) == compute_content_hash(dir2)

    def test_empty_dir(self, tmp_path: Path):
        """Empty directory produces a valid hash."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        result = compute_content_hash(skill_dir)
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", result)

    def test_single_file(self, tmp_path: Path):
        """Single file produces a valid hash."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Only file")

        result = compute_content_hash(skill_dir)
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", result)


class TestWriteSkillMetadataContentHash:
    """Tests for content_hash parameter in write_skill_metadata."""

    def test_includes_content_hash(self, tmp_path: Path):
        """content_hash is written when provided."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        handle = ParsedHandle(is_local=True, name="test", local_path=skill_dir)
        write_skill_metadata(
            skill_dir,
            handle,
            tmp_path,
            "claude",
            "test",
            content_hash="sha256:abc123",
        )

        meta = read_skill_metadata(skill_dir)
        assert meta is not None
        assert meta["content_hash"] == "sha256:abc123"

    def test_omits_hash_when_none(self, tmp_path: Path):
        """content_hash key is absent when not provided."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        handle = ParsedHandle(is_local=True, name="test", local_path=skill_dir)
        write_skill_metadata(skill_dir, handle, tmp_path, "claude", "test")

        meta = read_skill_metadata(skill_dir)
        assert meta is not None
        assert "content_hash" not in meta
