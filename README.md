# Media Auto Relink

A community Python script for **DaVinci Resolve** that reconnects media when a project moves between computers, operating systems, or mounted drives.

**Status:** v0.2 native review-window preview. Not yet verified in every Resolve version. Test on a duplicate project first.

## How it works

Configure a local **Workspace Folder**, then open an imported Resolve project. The script reads original media paths where Resolve exposes them, locates the matching workspace-relative path on your computer, and calls Resolve's media-pool relink function for the exact destination folder.

Example:

- Original: `D:\\Studio Workspace\\Projects\\Episode 12\\VO\\intro.wav`
- Local workspace: `/Volumes/Media/Studio Workspace`
- Expected: `/Volumes/Media/Studio Workspace/Projects/Episode 12/VO/intro.wav`

A clip from another project is handled the same way. Media in shared folders also works. No whole-drive or all-project deep search is used.

**Matching policy:** preserve every path segment following the workspace-folder name. If a source path lacks that anchor, the clip is reported as unresolved. Filename-only fallback matching is deliberately disabled.

## Requirements

- DaVinci Resolve with Python scripting support, on macOS (initial target). Resolve's Python scripting API must be available.
- Python 3 compatible with your installed Resolve.
- Identical relative directory structure between sender and recipient.
- Workspace folder must be the *local* root containing project folders and shared asset directories.

## Install

1. Download `MediaAutoRelink.py`, `media_auto_relink_core.py`, and `media_auto_relink_ui.py` into the same directory.
2. Place those files in Resolve's **Utility Scripts** directory. On macOS this is typically `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/`. Create the directory if needed; installations may vary.
3. Restart DaVinci Resolve and open the imported project.
4. Use **Workspace > Scripts > MediaAutoRelink** (menu location varies by Resolve version).
5. On first use, choose your **Workspace Folder** in Resolve's folder picker.
6. Use the native review window to confirm individual proposed matches, skip others, or select **Confirm All Exact**. Only **Apply Confirmed Relinks** starts relinking. Cancel changes nothing.

If file dialogs are unavailable in the embedded Python environment, edit `~/.media-auto-relink/config.json` manually, e.g.:

```json
{
  "workspace_folder": "/Volumes/Media/Studio Workspace",
  "preview_only": true
}
```

Version 0.2 uses the review window for confirmation rather than the old `preview_only` switch. The legacy setting may still be present but does not control the new review window. The script never saves the Resolve project automatically.

## Behavior and safeguards

- Exact expected paths are checked first; for missing workspace anchors, only immediate workspace subfolders are tested against the source's relative media-folder suffix. No recursive scan.
- Multiple clips located in the same destination folder are grouped into one `RelinkClips` call.
- Clips whose originals do not expose a usable path are explicitly reported.
- Existing online clips are skipped when their original path exists.
- Relink API return values are checked; a successful call **does not prove** that every clip became online, so the report re-checks clip paths afterward.
- Review decisions are staged until **Apply Confirmed Relinks**; cancel applies nothing.
- Reports are saved as JSON under `~/.media-auto-relink/reports/`.
- No automatic file replacement, deletion, proxy relinking, Fusion relinking, or DRP rewriting.
- Some effects, fonts, plug-ins, generators, and Fusion file loaders do not appear as ordinary media-pool clips and are not covered yet.

## Limitations

The Resolve scripting API can fail to expose original paths for certain offline clips or media types. Version 1 will report these files rather than guess. `RelinkClips` accepts a directory, not a per-clip path, so exact-path validation is done before calling the API; Resolve performs its own match inside that directory. Always verify the timeline after relinking.

## Development

Core path logic runs without DaVinci Resolve:

```bash
python3 -m unittest discover -s tests -v
```

Contributions and issue reports welcome. Include Resolve edition/version, OS, sanitized original/local paths, and the JSON report (review report paths before sharing publicly).

## License

MIT. See [LICENSE](LICENSE).

## Version 0.2 review window

The bundled `media_auto_relink_ui.py` displays a native Resolve/Fusion review window. Select a clip to inspect its original and proposed paths, then click **Confirm Selected**, **Skip Selected**, or **Confirm All Exact**. **Apply Confirmed Relinks** performs relinking for approved entries only. **Cancel** exits without applying changes. Matches with missing targets cannot be confirmed. A proposed candidate with a differently named project folder always requires individual approval.

**Testing status:** The window and scripting integration are committed but have not been run inside the user's Resolve installation. API or event adjustments may be needed depending on installed Resolve version. When the dialog is unavailable, the script reports the problem and does not relink clips.

### Review interface (v0.2.1)

- The review table fills the window; action buttons use compact fixed dimensions.
- Select multiple file rows with Command-click or Shift-click on macOS (where supported by your Resolve version).
- **Approve Selection:** stage only selected clips with an existing exact or suggested destination.
- **Leave for Manual:** mark selected clips to remain offline; they are not relinked.
- **Approve All Exact:** stage only clips whose full relative workspace paths match and whose target files exist. Suggested mismatches are excluded.
- **Clear Selection Choices:** clear decisions for selected rows.
- **Apply Approved Only:** relink approved clips only. Unapproved, manually deferred, and unavailable clips remain untouched.
- **Cancel:** apply nothing.

“Not found” means there is no validated local target. It does **not** necessarily mean the file is missing from the computer; it may be an unexposed Resolve path or a different directory structure.

This native UI code still needs validation in a running Resolve installation; its event support varies by version.
