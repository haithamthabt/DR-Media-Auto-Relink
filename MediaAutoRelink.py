"""Media Auto Relink — run from DaVinci Resolve's Workspace > Scripts menu.

Early preview. Operates only on Media Pool clips. Does not auto-save.
"""
import json
import os
from pathlib import Path
from datetime import datetime

from media_auto_relink_core import target_from_source, source_looks_like_path

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
    """Optional setup dialogs; edit config.json if tkinter is unavailable."""
    if config["workspace_folder"] and Path(config["workspace_folder"]).expanduser().is_dir():
        return config
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
        root = tk.Tk()
        root.withdraw()
        folder = filedialog.askdirectory(title="Select Workspace Folder")
        if folder:
            config["workspace_folder"] = folder
            config["preview_only"] = not messagebox.askyesno(
                "Media Auto Relink", "Apply relinks now? Choose No to preview first."
            )
            save_config(config)
        root.destroy()
    except Exception as exc:
        print("Folder dialog unavailable:", exc)
        print("Create config at:", CONFIG_FILE)
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
            row["status"] = "workspace_anchor_missing"
            continue
        row["expected"] = str(expected)
        if not expected.is_file():
            row["status"] = "expected_file_missing"
            continue
        row["status"] = "ready"
        groups.setdefault(str(expected.parent), []).append((item, row, expected, original))

    if not config.get("preview_only", True):
        for folder, entries in sorted(groups.items()):
            try:
                success = bool(pool.RelinkClips([e[0] for e in entries], folder))
            except Exception as exc:
                success = False
                for _, row, _, _ in entries:
                    row["error"] = str(exc)
            for item, row, expected, original in entries:
                row["status"] = (
                    report_status(item, expected, original)
                    if success else "api_relink_failed"
                )
    else:
        print("PREVIEW MODE: No clips were changed.")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = REPORT_DIR / ("relink-" + stamp + ".json")
    report = {
        "project": project.GetName(),
        "workspace_folder": str(workspace),
        "preview_only": bool(config.get("preview_only", True)),
        "clips": rows,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {}
    for row in rows:
        summary[row["status"]] = summary.get(row["status"], 0) + 1
    print("Media Auto Relink:", json.dumps(summary, indent=2))
    print("Report:", report_path)
    print("Review unverified entries manually. Save project yourself after verification.")


if __name__ == "__main__":
    main()
