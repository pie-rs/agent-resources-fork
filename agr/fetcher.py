"""GitHub download and skill installation."""

import logging
import warnings
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from urllib.parse import quote, urlparse, urlunparse

from agr.exceptions import (
    AgrError,
    AuthenticationError,
    RepoNotFoundError,
    SkillNotFoundError,
)
from agr.handle import (
    INSTALLED_NAME_SEPARATOR,
    LEGACY_REPO_DEPRECATION_WARNING,
    ParsedHandle,
    iter_repo_candidates,
)
from agr.metadata import (
    build_handle_id,
    compute_content_hash,
    read_skill_metadata,
    write_skill_metadata,
)
from agr.skill import (
    SKILL_MARKER,
    discover_skills_in_repo_listing,
    find_skill_in_repo,
    find_skill_in_repo_listing,
    is_valid_skill_dir,
    update_skill_md_name,
)
from agr.source import (
    DEFAULT_SOURCE_NAME,
    SourceConfig,
    SourceResolver,
    default_sources,
)
from agr.tool import DEFAULT_TOOL, ToolConfig

logger = logging.getLogger(__name__)


def _run_git(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command with consistent error handling.

    Wraps subprocess.run with standard options (capture output, text mode,
    no check) and ensures OSError is always converted to AgrError.

    Args:
        cmd: Full command list starting with "git".

    Returns:
        CompletedProcess with captured stdout/stderr.

    Raises:
        AgrError: If git cannot be executed (e.g., not installed).
    """
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as e:
        raise AgrError(f"Failed to run git: {type(e).__name__}") from None


def _skill_dir_matches_handle(skill_dir: Path, handle_ids: list[str] | None) -> bool:
    """Check whether a skill directory matches a handle via metadata."""
    if not handle_ids:
        return False
    meta = read_skill_metadata(skill_dir)
    if not meta:
        return False
    return meta.get("id") in handle_ids


def _find_local_name_conflicts(
    handle: ParsedHandle,
    skills_dir: Path,
    tool: ToolConfig,
    repo_root: Path | None,
    default_dest: Path,
) -> tuple[list[Path], bool]:
    """Find conflicting local installs with the same skill name.

    Returns a tuple of (conflict_paths, has_unknown_metadata).
    """
    handle_id = build_handle_id(handle, repo_root)
    conflicts: list[Path] = []
    has_unknown = False

    if tool.supports_nested:
        candidates = [skills_dir / "local" / handle.name]
    else:
        candidates = [skills_dir / handle.name, skills_dir / handle.to_installed_name()]

    for path in candidates:
        if tool.supports_nested and path == default_dest:
            continue
        if not is_valid_skill_dir(path):
            continue
        meta = read_skill_metadata(path)
        if meta:
            if meta.get("type") != "local":
                continue
            if meta.get("id") == handle_id:
                continue
            conflicts.append(path)
            continue
        has_unknown = True
        conflicts.append(path)

    return conflicts, has_unknown


def _find_existing_skill_dir(
    handle: ParsedHandle,
    skills_dir: Path,
    tool: ToolConfig,
    repo_root: Path | None,
    source: str | None = None,
) -> Path | None:
    """Find an existing installed skill directory for this handle."""
    if tool.supports_nested:
        skill_path = skills_dir / handle.to_skill_path(tool)
        return skill_path if is_valid_skill_dir(skill_path) else None

    handle_ids = _build_handle_ids(handle, repo_root, source)
    name_path = skills_dir / handle.name
    full_path = skills_dir / handle.to_installed_name()

    if is_valid_skill_dir(name_path) and _skill_dir_matches_handle(
        name_path, handle_ids
    ):
        return name_path
    if is_valid_skill_dir(full_path) and _skill_dir_matches_handle(
        full_path, handle_ids
    ):
        return full_path

    # Legacy fallback: flat installs used full path names
    if is_valid_skill_dir(full_path):
        return full_path

    return None


def _resolve_skill_destination(
    handle: ParsedHandle,
    skills_dir: Path,
    tool: ToolConfig,
    repo_root: Path | None,
    source: str | None = None,
) -> Path:
    """Resolve the destination path for installing a skill."""
    if tool.supports_nested:
        return skills_dir / handle.to_skill_path(tool)

    existing = _find_existing_skill_dir(handle, skills_dir, tool, repo_root, source)
    if existing:
        return existing

    name_path = skills_dir / handle.name
    if is_valid_skill_dir(name_path):
        return skills_dir / handle.to_installed_name()

    return name_path


def _get_github_token() -> str | None:
    """Get GitHub token from environment.

    Checks GITHUB_TOKEN first, then falls back to GH_TOKEN (used by gh CLI).

    Returns:
        Token string if set and non-empty, None otherwise.
    """
    for env_var in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(env_var, "")
        if token.strip():
            return token.strip()
    return None


def _is_github_source(source: SourceConfig) -> bool:
    """Return True if the source URL points to GitHub."""
    return "github.com" in source.url.lower()


def _get_default_branch(repo_url: str) -> str | None:
    """Return the default branch name for a remote repo, if detectable."""
    result = _run_git(["git", "ls-remote", "--symref", repo_url, "HEAD"])

    if result.returncode != 0:
        return None

    # Expected: "ref: refs/heads/main\tHEAD"
    for line in result.stdout.splitlines():
        if not line.startswith("ref:"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        if ref.startswith("refs/heads/"):
            return ref.replace("refs/heads/", "", 1)
    return None


@contextmanager
def downloaded_repo(
    source: SourceConfig, owner: str, repo_name: str
) -> Generator[Path, None, None]:
    """Download a git repo and yield the extracted directory.

    Args:
        source: Source configuration
        owner: Repo owner/username
        repo_name: Repository name

    Yields:
        Path to cloned repository directory

    Raises:
        RepoNotFoundError: If the repository doesn't exist
        AuthenticationError: If authentication fails (private repo without valid token)
        AgrError: If download fails
    """
    if shutil.which("git") is None:
        raise AgrError("git CLI not found. Install git to fetch remote skills.")

    repo_url = source.build_repo_url(owner, repo_name)
    repo_url = _apply_github_token(repo_url)
    default_branch = _get_default_branch(repo_url)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        repo_dir = tmp_path / "repo"

        result = _clone_repo(repo_url, repo_dir, partial=True, branch=default_branch)
        if result.returncode != 0 and _partial_clone_unsupported(result.stderr):
            _reset_repo_dir(repo_dir)
            result = _clone_repo(
                repo_url, repo_dir, partial=False, branch=default_branch
            )

        if result.returncode != 0:
            _raise_clone_error(
                result.stderr,
                owner,
                repo_name,
                source,
                stdout=result.stdout,
            )

        yield repo_dir


def _apply_github_token(repo_url: str) -> str:
    """Inject GitHub token into HTTPS URL if available."""
    token = _get_github_token()
    if not token:
        return repo_url
    parsed = urlparse(repo_url)
    if parsed.scheme != "https":
        return repo_url
    if not parsed.netloc.endswith("github.com"):
        return repo_url
    if "@" in parsed.netloc:
        return repo_url
    encoded = quote(token, safe="")
    netloc = f"{encoded}:x-oauth-basic@{parsed.netloc}"
    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def _clone_repo(
    repo_url: str, repo_dir: Path, partial: bool, branch: str | None
) -> subprocess.CompletedProcess:
    """Clone a repository using git, optionally with partial clone flags."""
    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--single-branch",
    ]
    if branch:
        cmd.extend(["--branch", branch])
    if partial:
        cmd.extend(["--filter=blob:none", "--no-checkout"])
    cmd.extend([repo_url, str(repo_dir)])
    return _run_git(cmd)


def _partial_clone_unsupported(stderr: str | None) -> bool:
    """Detect errors indicating partial clone is unsupported."""
    if not stderr:
        return False
    lowered = stderr.lower()
    return (
        ("unknown option" in lowered and "--filter" in lowered)
        or "filtering is not supported" in lowered
        or "does not support filtering" in lowered
        or "filtering not recognized" in lowered
    )


def _reset_repo_dir(repo_dir: Path) -> None:
    """Remove a partially created repo directory."""
    if repo_dir.exists():
        shutil.rmtree(repo_dir, ignore_errors=True)


def _raise_clone_error(
    stderr: str | None,
    owner: str,
    repo_name: str,
    source: SourceConfig,
    stdout: str | None = None,
) -> None:
    """Raise a friendly error based on git clone output."""
    message = "\n".join(
        part for part in ((stderr or "").strip(), (stdout or "").strip()) if part
    ).strip()
    lowered = message.lower()
    token_missing = _is_github_source(source) and not _get_github_token()

    if "authentication failed" in lowered or "permission denied" in lowered:
        if token_missing:
            raise AuthenticationError(
                f"Authentication failed for source '{source.name}'. "
                "Repository not found or requires authentication."
            ) from None
        raise AuthenticationError(
            f"Authentication failed for source '{source.name}'."
        ) from None
    if (
        "repository not found" in lowered
        or ("not found" in lowered and "repository" in lowered)
        or "does not exist" in lowered
    ):
        raise RepoNotFoundError(
            f"Repository '{owner}/{repo_name}' not found in source '{source.name}'."
        ) from None
    if "could not resolve host" in lowered:
        raise AgrError(
            f"Network error: could not resolve host for source '{source.name}'."
        ) from None
    if token_missing and (
        not lowered
        or "could not read username" in lowered
        or "terminal prompts disabled" in lowered
        or "authentication required" in lowered
        or "authorization failed" in lowered
        or "access denied" in lowered
    ):
        raise RepoNotFoundError(
            f"Repository '{owner}/{repo_name}' not found in source '{source.name}'."
        ) from None

    raise AgrError(f"Failed to clone repository from source '{source.name}'.") from None


def _git_list_files(repo_dir: Path) -> list[str]:
    """List files in the repo without checking out blobs."""
    result = _run_git(
        ["git", "-C", str(repo_dir), "ls-tree", "-r", "--name-only", "HEAD"]
    )
    if result.returncode != 0:
        raise AgrError("Failed to list repository files.")
    return [line for line in result.stdout.splitlines() if line.strip()]


def _checkout_full(repo_dir: Path) -> None:
    """Checkout the full repository."""
    checkout = _run_git(["git", "-C", str(repo_dir), "checkout", "-f", "main"])
    if checkout.returncode != 0:
        raise AgrError("Failed to checkout repository.")


def _checkout_sparse_paths(repo_dir: Path, rel_paths: list[Path]) -> None:
    """Checkout only the given paths using sparse checkout."""
    if not rel_paths:
        raise AgrError("No paths provided for sparse checkout.")
    init = _run_git(["git", "-C", str(repo_dir), "sparse-checkout", "init", "--cone"])
    if init.returncode != 0:
        raise AgrError("Failed to initialize sparse checkout.")
    cmd = ["git", "-C", str(repo_dir), "sparse-checkout", "set"]
    cmd.extend([rel_path.as_posix() for rel_path in rel_paths])
    set_cmd = _run_git(cmd)
    if set_cmd.returncode != 0:
        raise AgrError("Failed to set sparse checkout path.")
    _checkout_full(repo_dir)


def _checkout_sparse(repo_dir: Path, rel_path: Path) -> None:
    """Checkout only the given path using sparse checkout."""
    _checkout_sparse_paths(repo_dir, [rel_path])


def prepare_repo_for_skill(repo_dir: Path, skill_name: str) -> Path | None:
    """Prepare a repo so that only the skill path is checked out."""
    try:
        paths = _git_list_files(repo_dir)
        skill_rel = find_skill_in_repo_listing(paths, skill_name)
        if skill_rel is None:
            return None
        _checkout_sparse(repo_dir, Path(skill_rel))
        skill_path = repo_dir / skill_rel
        if not skill_path.exists():
            raise AgrError("Failed to checkout skill path.")
        return skill_path
    except AgrError:
        # Fallback: full checkout + scan
        _checkout_full(repo_dir)
        return find_skill_in_repo(repo_dir, skill_name)


def prepare_repo_for_skills(repo_dir: Path, skill_names: list[str]) -> dict[str, Path]:
    """Prepare a repo so multiple skill paths are checked out.

    Returns a mapping of skill name to resolved path for those found.
    Missing skills are omitted from the mapping.
    """
    unique_names = list(dict.fromkeys(skill_names))
    if not unique_names:
        return {}

    try:
        paths = _git_list_files(repo_dir)
        rel_paths: dict[str, Path] = {}
        for name in unique_names:
            skill_rel = find_skill_in_repo_listing(paths, name)
            if skill_rel is None:
                continue
            rel_paths[name] = Path(skill_rel)

        if rel_paths:
            _checkout_sparse_paths(repo_dir, list(rel_paths.values()))
            resolved = {
                name: repo_dir / rel_path for name, rel_path in rel_paths.items()
            }
            for path in resolved.values():
                if not path.exists():
                    raise AgrError("Failed to checkout skill path.")
            return resolved

        return {}
    except AgrError:
        # Fallback: full checkout + scan
        _checkout_full(repo_dir)
        resolved: dict[str, Path] = {}
        for name in unique_names:
            skill_path = find_skill_in_repo(repo_dir, name)
            if skill_path is not None:
                resolved[name] = skill_path
        return resolved


def list_remote_repo_skills(
    owner: str,
    repo_name: str,
    resolver: SourceResolver | None = None,
    source: str | None = None,
) -> list[str]:
    """List all skill names in a remote repository.

    Clones the repo and scans for SKILL.md files. Used to provide
    helpful suggestions when a two-part handle fails.

    Args:
        owner: Repository owner/username
        repo_name: Repository name
        resolver: Source resolver for finding the repo
        source: Explicit source name

    Returns:
        Sorted list of skill names found, or empty list on any error.
    """
    resolver = resolver or SourceResolver(default_sources(), DEFAULT_SOURCE_NAME)
    for source_config in resolver.ordered(source):
        try:
            with downloaded_repo(source_config, owner, repo_name) as repo_dir:
                paths = _git_list_files(repo_dir)
                return discover_skills_in_repo_listing(paths)
        except AgrError:
            continue
    return []


def _build_handle_ids(
    handle: ParsedHandle,
    repo_root: Path | None,
    source: str | None,
) -> list[str] | None:
    """Build handle IDs to match, including legacy ids."""
    if handle.is_local:
        return [build_handle_id(handle, repo_root)]
    handle_ids = [build_handle_id(handle, repo_root, source)]
    if source is None:
        handle_ids.append(build_handle_id(handle, repo_root, DEFAULT_SOURCE_NAME))
    if source == DEFAULT_SOURCE_NAME:
        handle_ids.append(build_handle_id(handle, repo_root))
    return handle_ids


def _copy_skill_to_destination(
    source: Path,
    dest: Path,
    handle: ParsedHandle,
    tool: ToolConfig,
    overwrite: bool,
    repo_root: Path | None,
    install_source: str | None = None,
) -> Path:
    """Copy skill source to destination with overwrite handling.

    Args:
        source: Source skill directory
        dest: Destination path
        handle: Parsed handle for naming
        tool: Tool configuration
        overwrite: Whether to overwrite existing
        repo_root: Repository root for metadata resolution (optional)

    Returns:
        Path to installed skill

    Raises:
        FileExistsError: If skill exists and not overwriting
    """
    if dest.exists() and not overwrite:
        raise FileExistsError(
            f"Skill already exists at {dest}. Use --overwrite to replace."
        )

    if dest.exists():
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)

    update_skill_md_name(dest, dest.name)
    hash_value = compute_content_hash(dest)
    write_skill_metadata(
        dest, handle, repo_root, tool.name, dest.name, install_source, hash_value
    )

    return dest


def install_skill_from_repo(
    repo_dir: Path,
    skill_name: str,
    handle: ParsedHandle,
    dest_dir: Path,
    tool: ToolConfig,
    repo_root: Path | None,
    overwrite: bool = False,
    install_source: str | None = None,
    skill_source: Path | None = None,
) -> Path:
    """Install a skill from a downloaded repository.

    Args:
        repo_dir: Path to extracted repository
        skill_name: Name of the skill to install
        handle: Parsed handle for naming
        dest_dir: Destination skills directory
        tool: Tool configuration for path structure
        repo_root: Repository root for metadata resolution (optional)
        overwrite: Whether to overwrite existing

    Returns:
        Path to installed skill

    Raises:
        SkillNotFoundError: If skill not found in repo
        FileExistsError: If skill exists and not overwriting
    """
    # Find the skill in the repo
    if skill_source is None:
        skill_source = find_skill_in_repo(repo_dir, skill_name)
    if skill_source is None:
        raise SkillNotFoundError(
            f"Skill '{skill_name}' not found in repository.\n"
            f"No directory named '{skill_name}' containing SKILL.md was found.\n"
            f"Hint: Create a skill at 'skills/{skill_name}/SKILL.md' or '{skill_name}/SKILL.md'"
        )

    skill_dest = _resolve_skill_destination(
        handle, dest_dir, tool, repo_root, install_source
    )

    return _copy_skill_to_destination(
        skill_source, skill_dest, handle, tool, overwrite, repo_root, install_source
    )


def install_skill_from_repo_to_tools(
    repo_dir: Path,
    skill_name: str,
    handle: ParsedHandle,
    tools: list[ToolConfig],
    repo_root: Path | None,
    overwrite: bool = False,
    install_source: str | None = None,
    skill_source: Path | None = None,
) -> dict[str, Path]:
    """Install a skill from a downloaded repo to multiple tools.

    On partial failure, already installed tools are rolled back.
    """
    if not tools:
        raise ValueError("No tools provided for installation")

    installed: dict[str, Path] = {}

    def _rollback() -> None:
        for rollback_path in installed.values():
            try:
                shutil.rmtree(rollback_path)
            except OSError as e:
                logger.warning(f"Failed to rollback {rollback_path}: {e}")

    for tool in tools:
        try:
            skills_dir = tool.get_skills_dir(repo_root) if repo_root else None
            if skills_dir is None:
                raise ValueError("repo_root is required for tool installation")
            path = install_skill_from_repo(
                repo_dir,
                skill_name,
                handle,
                skills_dir,
                tool,
                repo_root,
                overwrite,
                install_source=install_source,
                skill_source=skill_source,
            )
            installed[tool.name] = path
        except Exception:
            _rollback()
            raise

    return installed


def install_local_skill(
    source_path: Path,
    dest_dir: Path,
    tool: ToolConfig,
    overwrite: bool = False,
    repo_root: Path | None = None,
    handle: ParsedHandle | None = None,
) -> Path:
    """Install a local skill.

    Args:
        source_path: Path to local skill directory
        dest_dir: Destination skills directory
        tool: Tool configuration for path structure
        overwrite: Whether to overwrite existing
        repo_root: Repository root for metadata resolution (optional)
        handle: Optional pre-parsed handle for metadata and naming

    Returns:
        Path to installed skill

    Raises:
        SkillNotFoundError: If source is not a valid skill
        FileExistsError: If skill exists and not overwriting
        AgrError: If skill name contains reserved separator
    """
    # Validate source
    if not is_valid_skill_dir(source_path):
        raise SkillNotFoundError(
            f"'{source_path}' is not a valid skill (missing {SKILL_MARKER})"
        )

    # Validate skill name doesn't contain reserved separator (for flat tools)
    if not tool.supports_nested and INSTALLED_NAME_SEPARATOR in source_path.name:
        raise AgrError(
            f"Skill name '{source_path.name}' contains reserved sequence '{INSTALLED_NAME_SEPARATOR}'"
        )

    # Determine installed path using ParsedHandle for consistency
    handle = handle or ParsedHandle(
        is_local=True, name=source_path.name, local_path=source_path
    )
    if repo_root is None:
        repo_root = Path.cwd()

    default_dest = dest_dir / handle.to_skill_path(tool)
    if source_path.resolve() == default_dest.resolve() and is_valid_skill_dir(
        default_dest
    ):
        if read_skill_metadata(default_dest) is None:
            hash_value = compute_content_hash(default_dest)
            write_skill_metadata(
                default_dest,
                handle,
                repo_root,
                tool.name,
                default_dest.name,
                content_hash=hash_value,
            )
        return default_dest

    conflicts, has_unknown = _find_local_name_conflicts(
        handle, dest_dir, tool, repo_root, default_dest
    )
    if conflicts:
        locations = ", ".join(str(path) for path in conflicts)
        hint = ""
        if has_unknown:
            hint = " If this is a remote skill, run `agr sync` or reinstall it to add metadata."
        raise AgrError(
            f"Local skill name '{handle.name}' is already installed at {locations}. "
            "agr allows only one local skill with a given name. "
            "Rename the skill or remove the existing one."
            f"{hint}"
        )

    skill_dest = _resolve_skill_destination(handle, dest_dir, tool, repo_root)

    return _copy_skill_to_destination(
        source_path, skill_dest, handle, tool, overwrite, repo_root
    )


def install_remote_skill(
    handle: ParsedHandle,
    repo_root: Path | None,
    tool: ToolConfig,
    skills_dir: Path,
    *,
    overwrite: bool = False,
    resolver: SourceResolver | None = None,
    source: str | None = None,
    install_name: str | None = None,
) -> Path:
    """Install a remote skill to a specific tool directory."""
    if handle.is_local:
        raise ValueError("install_remote_skill requires a remote handle")

    resolver = resolver or SourceResolver(default_sources(), DEFAULT_SOURCE_NAME)
    owner = handle.username or ""
    repo_candidates = iter_repo_candidates(handle.repo)

    for repo_name, is_legacy in repo_candidates:
        for source_config in resolver.ordered(source):
            try:
                with downloaded_repo(source_config, owner, repo_name) as repo_dir:
                    skill_source = prepare_repo_for_skill(repo_dir, handle.name)
                    if skill_source is None:
                        continue
                    install_handle = (
                        ParsedHandle(
                            username=handle.username,
                            repo=handle.repo,
                            name=install_name,
                        )
                        if install_name
                        else handle
                    )
                    if is_legacy:
                        warnings.warn(
                            LEGACY_REPO_DEPRECATION_WARNING,
                            UserWarning,
                            stacklevel=2,
                        )
                    return install_skill_from_repo(
                        repo_dir,
                        handle.name,
                        install_handle,
                        skills_dir,
                        tool,
                        repo_root,
                        overwrite,
                        install_source=source_config.name,
                        skill_source=skill_source,
                    )
            except RepoNotFoundError:
                if source is not None:
                    raise
                continue

    raise SkillNotFoundError(
        f"Skill '{handle.name}' not found in sources: "
        f"{', '.join(s.name for s in resolver.ordered(source))}"
    )


def fetch_and_install(
    handle: ParsedHandle,
    repo_root: Path | None,
    tool: ToolConfig = DEFAULT_TOOL,
    overwrite: bool = False,
    resolver: SourceResolver | None = None,
    source: str | None = None,
    skills_dir: Path | None = None,
) -> Path:
    """Fetch and install a skill.

    Args:
        handle: Parsed handle (remote or local)
        repo_root: Repository root path (project installs) or None (global installs)
        tool: Tool configuration for path structure
        overwrite: Whether to overwrite existing

    Returns:
        Path to installed skill

    Raises:
        Various exceptions on failure
    """
    skills_dir = _resolve_skills_dir(skills_dir, repo_root, tool)

    if handle.is_local:
        # Local skill installation
        if handle.local_path is None:
            raise ValueError("Local handle missing path")

        source_path = handle.local_path
        if not source_path.is_absolute():
            base_path = repo_root or Path.cwd()
            source_path = (base_path / source_path).resolve()
        resolved_handle = ParsedHandle(
            is_local=True,
            name=handle.name,
            local_path=source_path,
        )

        return install_local_skill(
            source_path, skills_dir, tool, overwrite, repo_root, resolved_handle
        )

    # Remote skill installation
    return install_remote_skill(
        handle,
        repo_root,
        tool,
        skills_dir,
        overwrite=overwrite,
        resolver=resolver,
        source=source,
    )


def fetch_and_install_to_tools(
    handle: ParsedHandle,
    repo_root: Path | None,
    tools: list[ToolConfig],
    overwrite: bool = False,
    resolver: SourceResolver | None = None,
    source: str | None = None,
    skills_dirs: dict[str, Path] | None = None,
) -> dict[str, Path]:
    """Fetch skill once and install to multiple tools.

    This optimizes the common case of installing to multiple tools by
    downloading the repository only once.

    Args:
        handle: Parsed handle (remote or local)
        repo_root: Repository root path (project installs) or None (global installs)
        tools: List of tool configurations to install to
        overwrite: Whether to overwrite existing installations

    Returns:
        Dict mapping tool name to installed path

    Raises:
        Various exceptions on failure. On partial failure, already installed
        tools are rolled back (removed).
    """
    if not tools:
        raise ValueError("No tools provided for installation")

    installed: dict[str, Path] = {}

    def _rollback():
        """Remove all successfully installed skills."""
        for tool_name, rollback_path in installed.items():
            try:
                shutil.rmtree(rollback_path)
            except OSError as e:
                logger.warning(
                    f"Failed to rollback {tool_name} at {rollback_path}: {e}"
                )

    if handle.is_local:
        # Local: no download needed, just iterate with rollback
        for tool in tools:
            try:
                target_skills_dir = (
                    skills_dirs.get(tool.name) if skills_dirs is not None else None
                )
                installed[tool.name] = fetch_and_install(
                    handle,
                    repo_root,
                    tool,
                    overwrite,
                    resolver,
                    source,
                    skills_dir=target_skills_dir,
                )
            except Exception:
                _rollback()
                raise
        return installed

    # Remote: download once, install to all
    resolver = resolver or SourceResolver(default_sources(), DEFAULT_SOURCE_NAME)
    owner = handle.username or ""
    repo_candidates = iter_repo_candidates(handle.repo)

    for repo_name, is_legacy in repo_candidates:
        for source_config in resolver.ordered(source):
            try:
                with downloaded_repo(source_config, owner, repo_name) as repo_dir:
                    skill_source = prepare_repo_for_skill(repo_dir, handle.name)
                    if skill_source is None:
                        continue
                    for tool in tools:
                        try:
                            skills_dir = (
                                skills_dirs.get(tool.name)
                                if skills_dirs is not None
                                else None
                            )
                            if skills_dir is None:
                                if repo_root is None:
                                    raise ValueError(
                                        "repo_root is required when skills_dirs is not provided"
                                    )
                                skills_dir = tool.get_skills_dir(repo_root)
                            path = install_skill_from_repo(
                                repo_dir,
                                handle.name,
                                handle,
                                skills_dir,
                                tool,
                                repo_root,
                                overwrite,
                                install_source=source_config.name,
                                skill_source=skill_source,
                            )
                            installed[tool.name] = path
                        except Exception:
                            _rollback()
                            raise
                    if is_legacy:
                        warnings.warn(
                            LEGACY_REPO_DEPRECATION_WARNING,
                            UserWarning,
                            stacklevel=2,
                        )
                    return installed
            except RepoNotFoundError:
                if source is not None:
                    raise
                continue

    raise SkillNotFoundError(
        f"Skill '{handle.name}' not found in sources: "
        f"{', '.join(s.name for s in resolver.ordered(source))}"
    )


def uninstall_skill(
    handle: ParsedHandle,
    repo_root: Path | None,
    tool: ToolConfig = DEFAULT_TOOL,
    source: str | None = None,
    skills_dir: Path | None = None,
) -> bool:
    """Uninstall a skill.

    Args:
        handle: Parsed handle identifying the skill
        repo_root: Repository root path (project installs) or None (global installs)
        tool: Tool configuration for path structure

    Returns:
        True if removed, False if not found
    """
    resolved_dir = _resolve_skills_dir(skills_dir, repo_root, tool)
    skill_path = _find_existing_skill_dir(handle, resolved_dir, tool, repo_root, source)

    if not skill_path:
        return False

    shutil.rmtree(skill_path)

    # Clean up empty parent directories for nested structures
    if tool.supports_nested:
        _cleanup_empty_parents(skill_path.parent, resolved_dir)

    return True


def _resolve_skills_dir(
    skills_dir: Path | None, repo_root: Path | None, tool: ToolConfig
) -> Path:
    """Resolve skills directory from explicit path or repo_root + tool config.

    Args:
        skills_dir: Explicit skills directory, if provided.
        repo_root: Repository root path (project installs) or None (global installs).
        tool: Tool configuration for deriving the skills directory.

    Returns:
        Resolved skills directory path.

    Raises:
        ValueError: If both skills_dir and repo_root are None.
    """
    if skills_dir is not None:
        return skills_dir
    if repo_root is None:
        raise ValueError("repo_root is required when skills_dir is not provided")
    return tool.get_skills_dir(repo_root)


def _cleanup_empty_parents(path: Path, stop_at: Path) -> None:
    """Remove empty parent directories up to stop_at.

    Args:
        path: Starting path to clean
        stop_at: Directory to stop at (not removed)
    """
    # Resolve symlinks to ensure proper path comparison
    path = path.resolve()
    stop_at = stop_at.resolve()
    current = path

    while current != stop_at and current.exists():
        # Safety: ensure we're still within stop_at
        try:
            current.relative_to(stop_at)
        except ValueError:
            break  # Escaped the directory

        if current.is_dir() and not any(current.iterdir()):
            try:
                current.rmdir()
            except OSError:
                break  # Permission error or other issue
            current = current.parent
        else:
            break


def get_installed_skills(repo_root: Path, tool: ToolConfig = DEFAULT_TOOL) -> list[str]:
    """Get list of installed skill names.

    Args:
        repo_root: Repository root path
        tool: Tool configuration for path structure

    Returns:
        List of installed skill directory names (flat) or paths (nested)
    """
    skills_dir = tool.get_skills_dir(repo_root)

    if not skills_dir.exists():
        return []

    if tool.supports_nested:
        # For nested tools, recursively find all SKILL.md files
        skills = []
        for skill_md in skills_dir.rglob(SKILL_MARKER):
            skill_path = skill_md.parent.relative_to(skills_dir)
            skills.append(str(skill_path))
        return skills
    else:
        # For flat tools, just list top-level directories
        return [
            d.name
            for d in skills_dir.iterdir()
            if d.is_dir() and (d / SKILL_MARKER).exists()
        ]


def is_skill_installed(
    handle: ParsedHandle,
    repo_root: Path | None,
    tool: ToolConfig = DEFAULT_TOOL,
    source: str | None = None,
    skills_dir: Path | None = None,
) -> bool:
    """Check if a skill is installed.

    Args:
        handle: Parsed handle identifying the skill
        repo_root: Repository root path (project installs) or None (global installs)
        tool: Tool configuration for path structure

    Returns:
        True if installed
    """
    resolved_dir = _resolve_skills_dir(skills_dir, repo_root, tool)
    skill_path = _find_existing_skill_dir(handle, resolved_dir, tool, repo_root, source)
    return bool(skill_path and is_valid_skill_dir(skill_path))
