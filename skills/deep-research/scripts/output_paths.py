"""Project-local output path policy for deep-research runs."""

import hashlib
import os
import subprocess
import time
import unicodedata
from pathlib import Path


RUN_PREFIX = "deep-research-"
RESEARCH_DIR_NAME = "research"
FALLBACK_NAME_MAX = 255
GIT_DISCOVERY_TIMEOUT_SECONDS = 5
PREPARED_RUN_CLAIM = ".raw-run.claim"
GIT_REBINDING_ENV_VARS = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_WORK_TREE",
)


def _launch_relative_path(value, launch_cwd):
    if not str(value).strip():
        raise ValueError("path must not be blank")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path(launch_cwd) / path
    return path.resolve()


def resolve_output_directory(output_dir, launch_cwd):
    """Resolve an explicit output override from the captured launch cwd."""
    return _launch_relative_path(output_dir, launch_cwd)


def resolve_launch_directory(explicit_launch_cwd, process_cwd):
    """Resolve and validate a caller-captured launch directory."""
    if explicit_launch_cwd is None:
        return Path(process_cwd).resolve()
    launch_cwd = _launch_relative_path(explicit_launch_cwd, process_cwd)
    if not launch_cwd.is_dir():
        raise ValueError(f"launch directory is not an existing directory: {launch_cwd}")
    return launch_cwd


def resolve_project_root(launch_cwd, explicit_root=None):
    """Resolve explicit root, Git top-level, or the captured cwd in that order."""
    launch_cwd = Path(launch_cwd).resolve()
    if explicit_root is not None:
        root = _launch_relative_path(explicit_root, launch_cwd)
        if not root.is_dir():
            raise ValueError(f"project root is not an existing directory: {root}")
        return root

    git_env = os.environ.copy()
    for name in GIT_REBINDING_ENV_VARS:
        git_env.pop(name, None)

    try:
        result = subprocess.run(
            ["git", "-C", str(launch_cwd), "rev-parse", "--show-toplevel"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=GIT_DISCOVERY_TIMEOUT_SECONDS,
            env=git_env,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return launch_cwd

    if result.returncode == 0 and result.stdout.strip():
        root = Path(result.stdout.strip()).resolve()
        try:
            launch_cwd.relative_to(root)
        except ValueError:
            return launch_cwd
        if root.is_dir():
            return root
    return launch_cwd


def validate_prepared_run_directory(output_dir, topic):
    """Validate a skill-reserved run before connector files may be written."""
    output_dir = Path(output_dir)
    if not output_dir.is_dir():
        raise ValueError(f"prepared run is not an existing directory: {output_dir}")

    allowed = {"_topic.txt", "research-plan.md"}
    unexpected = sorted(path.name for path in output_dir.iterdir() if path.name not in allowed)
    if unexpected:
        raise ValueError(
            "prepared run already contains non-plan artifacts: "
            + ", ".join(unexpected)
        )

    topic_path = output_dir / "_topic.txt"
    try:
        reserved_topic = topic_path.read_text(encoding="utf-8").rstrip("\n")
    except (FileNotFoundError, IsADirectoryError) as exc:
        raise ValueError(f"prepared run is missing topic marker: {topic_path}") from exc
    if reserved_topic != topic:
        raise ValueError(
            f"prepared run topic mismatch: reserved {reserved_topic!r}, requested {topic!r}"
        )

    plan_path = output_dir / "research-plan.md"
    try:
        plan_text = plan_path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError) as exc:
        raise ValueError(f"prepared run is missing research plan: {plan_path}") from exc
    if not plan_text.strip():
        raise ValueError(f"prepared run research plan is empty: {plan_path}")


def claim_prepared_run_directory(output_dir, topic):
    """Validate and atomically claim a prepared run for one connector process."""
    validate_prepared_run_directory(output_dir, topic)
    claim_path = Path(output_dir) / PREPARED_RUN_CLAIM
    try:
        descriptor = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError(f"prepared run is already claimed: {claim_path}") from exc
    try:
        os.write(descriptor, (topic + "\n").encode("utf-8"))
    finally:
        os.close(descriptor)


def topic_slug(topic):
    """Return a normalized, deterministic directory slug for a topic."""
    normalized = unicodedata.normalize("NFKC", topic).casefold()
    parts = []
    pending_separator = False
    for char in normalized:
        if char.isalnum():
            if pending_separator and parts:
                parts.append("-")
            parts.append(char)
            pending_separator = False
        else:
            pending_separator = True
    slug = "".join(parts)
    if slug:
        return slug
    digest = hashlib.sha256(topic.encode("utf-8")).hexdigest()[:8]
    return f"topic-{digest}"


def _filesystem_name_max(path):
    try:
        value = os.pathconf(str(path), "PC_NAME_MAX")
    except (AttributeError, OSError, ValueError):
        return FALLBACK_NAME_MAX
    return value if isinstance(value, int) and value > 0 else FALLBACK_NAME_MAX


def _truncate_utf8(value, byte_limit):
    if byte_limit <= 0:
        return ""
    encoded = value.encode("utf-8")
    if len(encoded) <= byte_limit:
        return value
    return encoded[:byte_limit].decode("utf-8", errors="ignore")


def _run_component(slug, run_date, attempt, name_max):
    suffix = "" if attempt == 1 else f"-{attempt:02d}"
    fixed = f"{RUN_PREFIX}{run_date}{suffix}"
    slug_budget = name_max - len(fixed.encode("utf-8")) - 1
    if slug_budget < 1:
        raise ValueError(
            f"filesystem name limit {name_max} is too small for a research run"
        )
    trimmed_slug = _truncate_utf8(slug, slug_budget)
    if not trimmed_slug:
        raise ValueError(
            f"filesystem name limit {name_max} is too small for a research run slug"
        )
    return f"{RUN_PREFIX}{trimmed_slug}-{run_date}{suffix}"


def allocate_run_directory(project_root, topic, run_date=None, name_max=None):
    """Atomically reserve and return a unique project-local research run."""
    project_root = Path(project_root).resolve()
    research_root = project_root / RESEARCH_DIR_NAME
    try:
        research_root.mkdir(exist_ok=True)
    except FileExistsError as exc:
        raise ValueError(
            f"research path is not a directory: {research_root}"
        ) from exc
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise ValueError(
            f"project root is not an existing directory: {project_root}"
        ) from exc

    run_date = run_date or time.strftime("%Y-%m-%d")
    name_max = name_max or _filesystem_name_max(research_root)
    slug = topic_slug(topic)

    attempt = 1
    while True:
        component = _run_component(slug, run_date, attempt, name_max)
        candidate = research_root / component
        try:
            candidate.mkdir(exist_ok=False)
            return candidate
        except FileExistsError:
            attempt += 1
