"""Media Auto Relink — run from DaVinci Resolve's Workspace > Scripts menu.

Early preview. Operates only on Media Pool clips. Does not auto-save.
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from media_auto_relink_core import target_from_source, source_looks_like_path
from media_auto_relink_ui import review_window

APP_DIR = Path.home() / ".media-auto-relink"
CONFIG_FILE = APP_DIR / "config.json"
REPORT_DIR = APP_DIR / "reports"


def load_config():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    default = {"workspace_folder": "", "preview_only": True}
    if CONFIG_FILE.exists():
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            default.update({k: raw[k] for k in default if k in raw})
        except (OSError, ValueError, TypeError) as exc:
            print("Media Auto Relink: Cannot read config:", exc)
    return default


def save_config(config):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def configure(config):
    """Select workspace with Resolve/Fusion's own dialog (no tkinter needed)."""
    if config["workspace_folder"] and Path(config["workspace_folder"]).expanduser().is_dir():
        return config

    folder = None
    try:
        api = globals().get("resolve")
        if not api:
            import DaVinciResolveScript as dvr
            api = dvr.scriptapp("Resolve")
        fusion = api.Fusion() if api else None
        if fusion:
            folder = fusion.RequestDir()
    except Exception as exc:
        print("Resolve/Fusion folder dialog unavailable:", exc)

    if folder and Path(folder).is_dir():
        config["workspace_folder"] = folder
        # Keep preview enabled by default; user explicitly changes config for live relink.
        config["preview_only"] = True
        save_config(config)
        print("Workspace Folder saved:", folder)
    else:
        print("No folder selected. Set Workspace Folder in:", CONFIG_FILE)
        print('Example: {"workspace_folder": "/Volumes/Media/Studio Workspace", "preview_only": true}')
    return config


def all_media_items(folder):
    for item in folder.GetClipList() or []:
        yield item
    for child in folder.GetSubFolderList() or []:
        yield from all_media_items(child)


def get_original_path(item):
    try:
        props = item.GetClipProperty() or {}
        path = props.get("File Path") or props.get("FilePath") or ""
        if isinstance(path, str) and source_looks_like_path(path):
            return path
    except Exception:
        pass
    return ""


def report_status(item, expected, original):
    current = get_original_path(item)
    # A relink call returning True is not definitive. Determine whether
    # Resolve now points at an existing expected pathname.
    if current:
        try:
            if Path(current).resolve() == expected.resolve() and expected.is_file():
                return "verified"
        except (OSError, ValueError):
            pass
    if current != original and current and Path(current).is_file():
        return "path_changed_needs_review"
    return "unverified"


def propose_limited_candidate(source, workspace):
    """Try a uniquely matching immediate project folder, without recursive search."""
    from media_auto_relink_core import normalized_parts
    parts = normalized_parts(source)
    if len(parts) < 3:
        return None
    # The source project folder is usually followed by a known subdivision.
    # Preserve this subdivision and file name; only the project name can differ.
    folders = {"videos", "video", "vo", "assets", "audio", "music", "effects", "sfx", "sounds effects", "sound effects"}
    candidates = []
    for ix, part in enumerate(parts[:-1]):
        if part.casefold() not in folders:
            continue
        tail = parts[ix:]
        if not tail or ".." in tail:
            continue
        # Look in immediate children only, allowing differing project folder names.
        for child in workspace.iterdir():
            if not child.is_dir():
                continue
            target = child.joinpath(*tail)
            if target.is_file():
                candidates.append(target)
    # A suggestion is allowed only if one unambiguous path matches.
    unique = list(dict.fromkeys(candidates))
    return unique[0] if len(unique) == 1 else None


def main():
    config = configure(load_config())
    workspace_text = config.get("workspace_folder", "")
    workspace = Path(workspace_text).expanduser() if workspace_text else None
    if not workspace or not workspace.is_dir():
        print("Media Auto Relink: Set an existing Workspace Folder in", CONFIG_FILE)
        return

    # Resolve injects 'resolve' in some execution environments.
    api = globals().get("resolve")
    if not api:
        try:
            import DaVinciResolveScript as dvr
            api = dvr.scriptapp("Resolve")
        except Exception as exc:
            print("Unable to connect to Resolve scripting:", exc)
            return
    if not api:
        print("Could not connect to DaVinci Resolve.")
        return

    project = api.GetProjectManager().GetCurrentProject()
    if not project:
        print("Open a Resolve project first.")
        return
    pool = project.GetMediaPool()
    if not pool:
        print("Media pool unavailable.")
        return

    rows = []
    groups = {}
    workspace_warnings = []
    items = list(all_media_items(pool.GetRootFolder()))
    for item in items:
        original = get_original_path(item)
        name = item.GetName()
        row = {"name": name, "original": original, "expected": None, "status": None}
        rows.append(row)
        if not original:
            row["status"] = "original_path_unavailable"
            continue
        # If the original file exists, do not relink it.
        if Path(original).is_file():
            row["status"] = "already_online"
            continue
        expected = target_from_source(original, workspace)
        if expected is None:
            row["status"] = "workspace_structure_mismatch"
            row["warning"] = "Original source path does not contain the configured Workspace Folder name."
            row["action"] = "Ask the editor to verify the standard workspace layout and re-export the project."
            candidate = propose_limited_candidate(original, workspace)
            if candidate is not None:
                row["expected"] = str(candidate)
                row["status"] = "suggested_review"
                row["warning"] = "Project folder differs. User approval required."
                groups.setdefault(str(candidate.parent), []).append((item, row, candidate, original))
            workspace_warnings.append(row)
            continue
        row["expected"] = str(expected)
        if not expected.is_file():
            row["status"] = "expected_file_missing"
            continue
        row["status"] = "ready"
        groups.setdefault(str(expected.parent), []).append((item, row, expected, original))

    # Preview diagnostics: show a few source paths to troubleshoot root mismatch.
    # No recursive disk search and no automatic guesses about filename matches.
    if config.get("preview_only", True):
        print("Workspace selected:", str(workspace))
        failures = [r for r in rows if r["status"] in (
            "workspace_anchor_missing", "original_path_unavailable",
            "expected_file_missing")]
        for row in failures[:8]:
            print("Diagnostic:", row["status"], "| clip:", repr(row["name"]),
                  "| original:", repr(row["original"]),
                  "| expected:", repr(row["expected"]))
        if len(failures) > 8:
            print("More diagnostic entries saved in JSON report:", len(failures) - 8)

    # Review everything in one native Resolve/Fusion window.
    approved = None
    try:
        bmd_api = globals().get("bmd")
        if bmd_api is None:
            try:
                import BlackmagicFusion as bmd_api
            except ImportError:
                import DaVinciResolveScript as bmd_api
        fusion = api.Fusion()
        approved = review_window(fusion, bmd_api, rows, workspace)
    except Exception as exc:
        print("Native review window unavailable; no files changed:", exc)
        approved = None

    if approved is None:
        print("Review cancelled. No files were relinked.")
    else:
        approved_ids = {ix for ix in approved if isinstance(ix, int) and 0 <= ix < len(rows)}
        # Rebuild groups from the reviewed rows, including newly located media.
        apply_groups = {}
        for ix in approved_ids:
            row = rows[ix]
            if row["status"] not in ("ready", "suggested_review", "located_review"):
                continue
            expected = Path(row.get("expected") or "")
            if not expected.is_file():
                row["status"] = "expected_file_missing"
                continue
            apply_groups.setdefault(str(expected.parent), []).append(
                (items[ix], row, expected, row.get("original", ""))
            )
        for folder, selected in sorted(apply_groups.items()):
            try:
                success = bool(pool.RelinkClips([e[0] for e in selected], folder))
            except Exception as exc:
                success = False
                for _, row, _, _ in selected:
                    row["error"] = str(exc)
            for item, row, expected, original in selected:
                row["status"] = (report_status(item, expected, original)
                                 if success else "api_relink_failed")
        for ix, row in enumerate(rows):
            if ix not in approved_ids and row["status"] in ("ready", "suggested_review", "located_review"):
                row["status"] = "skipped_or_not_confirmed"

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = REPORT_DIR / ("relink-" + stamp + ".json")
    report = {
        "project": project.GetName(),
        "workspace_folder": str(workspace),
        "review_cancelled": approved is None,
        "preview_only": approved is None,
        "clips": rows,
        "workspace_warnings": workspace_warnings,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {}
    for row in rows:
        summary[row["status"]] = summary.get(row["status"], 0) + 1
    print("Media Auto Relink:", json.dumps(summary, indent=2))
    if workspace_warnings:
        print("\\n" + "=" * 60)
        print("WORKSPACE STRUCTURE WARNING:", len(workspace_warnings), "clips")
        print("No automatic folder-name substitutions were made.")
        print("Ask the editor to verify the workspace layout.")
        for row in workspace_warnings[:10]:
            print(" -", row["name"], "| original:", row["original"])
        if len(workspace_warnings) > 10:
            print("Additional warnings in report:", len(workspace_warnings) - 10)
        print("=" * 60 + "\\n")
    print("Report:", report_path)
    print("Review unverified entries manually. Save project yourself after verification.")


if __name__ == "__main__":
    main()
