"""Pure path mapping; does not depend on DaVinci Resolve."""
from pathlib import Path, PureWindowsPath
import re


def normalized_parts(path):
    """Split Windows or POSIX absolute path into stable components."""
    if not isinstance(path, str) or not path.strip():
        return []
    value = path.strip().strip('"').replace("\\", "/")
    return [part for part in value.split("/") if part not in ("", ".")]


def workspace_relative(source_path, workspace_name):
    """Return source path relative to the last workspace anchor, or None.

    Fail closed for traversal, missing anchors, and ambiguous empty paths.
    """
    parts = normalized_parts(source_path)
    if not parts or not workspace_name or "/" in workspace_name or "\\" in workspace_name:
        return None
    indices = [i for i, part in enumerate(parts) if part.casefold() == workspace_name.casefold()]
    if not indices:
        return None
    tail = parts[indices[-1] + 1:]
    if not tail or any(part == ".." for part in tail):
        return None
    return tuple(tail)


def target_from_source(source_path, workspace):
    root = Path(workspace).expanduser().resolve()
    rel = workspace_relative(source_path, root.name)
    if rel is None:
        return None
    candidate = root.joinpath(*rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def source_looks_like_path(value):
    if not isinstance(value, str):
        return False
    value = value.strip()
    return bool(re.match(r"^(?:[A-Za-z]:[\\/]|/|\\\\)", value))
