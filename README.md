# Media Auto Relink

A community Python script for **DaVinci Resolve** that reconnects media when a project moves between computers, operating systems, or mounted drives.

**Status:** early preview (v0.1). Test on a duplicate project first. It is not yet a packaged native Resolve panel.

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

1. Download `MediaAutoRelink.py` and `media_auto_relink_core.py` into the same directory.
2. Place those files in Resolve's **Utility Scripts** directory. On macOS this is typically `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/`. Create the directory if needed; installations may vary.
3. Restart DaVinci Resolve and open the imported project.
4. Use **Workspace > Scripts > MediaAutoRelink** (menu location varies by Resolve version).
5. On first use, enter your **Workspace Folder** and optionally choose preview mode.
6. Inspect the report, then run again with changes enabled.

If file dialogs are unavailable in the embedded Python environment, edit `~/.media-auto-relink/config.json` manually, e.g.:

```json
{
  "workspace_folder": "/Volumes/Media/Studio Workspace",
  "preview_only": true
}
```

Set `preview_only` to `false` after validating the plan. Run again whenever needed. The script never saves the Resolve project automatically.

## Behavior and safeguards

- Only expected paths are checked: no recursive scan.
- Multiple clips located in the same destination folder are grouped into one `RelinkClips` call.
- Clips whose originals do not expose a usable path are explicitly reported.
- Existing online clips are skipped when their original path exists.
- Relink API return values are checked; a successful call **does not prove** that every clip became online, so the report re-checks clip paths afterward.
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
