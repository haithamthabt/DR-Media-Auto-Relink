"""Compact native Fusion UI review for Media Auto Relink.

All choices are staged. Apply only passes explicitly approved indices to caller.
"""

def review_window(fusion, bmd, rows, workspace):
    import os
    from pathlib import Path
    ui = fusion.UIManager
    dispatcher = bmd.UIDispatcher(ui)
    win = dispatcher.AddWindow(
        {"ID": "MARReview", "WindowTitle": "Media Auto Relink — Review",
         "Geometry": [40, 35, 1120, 660], "MinimumSize": [800, 510]},
        ui.VGroup({"Spacing": 4, "Margin": 8}, [
            ui.HGroup({"Weight": 0, "Spacing": 8}, [
                ui.Label({"ID": "WorkspaceLabel", "Text": "Workspace: " + str(workspace), "Weight": 1})
            ]),
            ui.Label({"ID": "Summary", "Text": "", "Weight": 0, "MaximumSize": [1000, 22]}),
            ui.HGroup({"Weight": 0, "Spacing": 8}, [
                ui.Button({"ID": "Apply", "Text": "Apply Approved Files", "MaximumSize": [185, 30]}),
                ui.Button({"ID": "CloseButton", "Text": "Cancel", "MaximumSize": [100, 30]}),
                ui.Label({"ID": "Staged", "Text": "", "Weight": 1})
            ]),
            ui.HGroup({"Weight": 0, "Spacing": 6}, [
                ui.Label({"Text": "Show:", "MaximumSize": [42, 25]}),
                ui.ComboBox({"ID": "Filter", "MaximumSize": [185, 28]}),
                ui.Button({"ID": "ApproveVisible", "Text": "Approve Shown Matches", "MaximumSize": [190, 28]}),
                ui.Button({"ID": "ClearVisible", "Text": "Reset Shown Decisions", "MaximumSize": [175, 28]}),
                ui.Button({"ID": "Locate", "Text": "Locate in Folder...", "MaximumSize": [160, 28]})
            ]),
            ui.Tree({"ID": "Matches", "Weight": 1, "MaximumSize": [1100, 385], "SelectionMode": "ExtendedSelection",
                     "SortingEnabled": False, "AlternatingRowColors": True}),
            ui.Label({"ID": "Details", "Text": "Click a file to inspect paths. Select multiple rows with Cmd-click.", "Weight": 0,
                      "WordWrap": True, "MaximumSize": [1100, 45]}),
            ui.HGroup({"Weight": 0, "Spacing": 8}, [
                ui.Button({"ID": "Confirm", "Text": "Approve Selected", "MaximumSize": [155, 27]}),
                ui.Button({"ID": "Skip", "Text": "Exclude Selected", "MaximumSize": [155, 27]}),
                ui.Button({"ID": "ConfirmExact", "Text": "Approve All Exact", "MaximumSize": [155, 27]}),
                ui.Button({"ID": "Reset", "Text": "Reset Selected Decisions", "MaximumSize": [180, 27]}),
                ui.Label({"ID": "ToolbarSpacer", "Text": "", "Weight": 1})
            ])
        ])
    )
    widgets = win.GetItems()
    tree = widgets["Matches"]
    tree.SetHeaderLabels(["Decision", "Match", "Filename", "Original path", "Suggested local path"])
    for column, width in enumerate([110, 145, 190, 265, 300]):
        try:
            tree.SetColumnWidth(column, width)
        except Exception:
            pass

    def match_label(row):
        return {
            "ready": "Exact path",
            "suggested_review": "Folder differs — review",
            "located_review": "Found in selected folder — review",
            "multiple_candidates": "Multiple matches — manual",
            "original_path_unavailable": "No source path",
            "workspace_structure_mismatch": "Outside workspace",
            "expected_file_missing": "File not found",
            "already_online": "Already linked",
        }.get(row["status"], row["status"].replace("_", " "))

    def decision_label(index):
        if index in decisions:
            return "APPROVE" if decisions[index] == "confirm" else "MANUAL"
        if rows[index]["status"] == "ready":
            return "Ready"
        if rows[index]["status"] in ("suggested_review", "located_review"):
            return "Needs review"
        if rows[index]["status"] == "already_online":
            return "Online"
        return "Not found"

    decisions = {}
    entry_map = {}
    displayed = []
    filter_choices = ["All files", "Needs review", "Exact matches", "Not found / other", "Already linked", "Approved", "Excluded"]
    for label in filter_choices:
        widgets["Filter"].AddItem(label)
    widgets["Filter"].CurrentIndex = 0
    sorting = {"column": 1, "descending": False}

    def included(index):
        row = rows[index]
        which = widgets["Filter"].CurrentIndex
        if which == 1:
            return row["status"] in ("suggested_review", "located_review")
        if which == 2:
            return row["status"] == "ready"
        if which == 3:
            return row["status"] not in ("ready", "suggested_review", "located_review", "already_online")
        if which == 4:
            return row["status"] == "already_online"
        if which == 5:
            return decisions.get(index) == "confirm"
        if which == 6:
            return decisions.get(index) == "skip"
        return True

    def order_key(index):
        row = rows[index]
        column = sorting["column"]
        if column == 0:
            return (decision_label(index).casefold(), row["name"].casefold())
        if column == 1:
            return (match_label(row).casefold(), row["name"].casefold())
        if column == 2:
            return (row["name"].casefold(), index)
        if column == 3:
            return (str(row.get("original") or "").casefold(), index)
        return (str(row.get("expected") or "").casefold(), index)

    def fill_table():
        # Rebuild on filter or sort changes; decisions remain keyed to original indices.
        tree.Clear()
        entry_map.clear()
        displayed[:] = sorted((ix for ix in range(len(rows)) if included(ix)), key=order_key, reverse=sorting["descending"])
        for ix in displayed:
            row = rows[ix]
            entry = tree.NewItem()
            entry.Text[0] = decision_label(ix)
            entry.Text[1] = match_label(row)
            entry.Text[2] = str(row["name"])
            entry.Text[3] = str(row.get("original") or "")
            entry.Text[4] = str(row.get("expected") or "")
            tree.AddTopLevelItem(entry)
            entry_map[ix] = entry

    def selected_indices():
        """Read the actual visible highlight from each TreeItem.

        Some Resolve/Fusion Python bridges return opaque TreeItem wrappers from
        SelectedItems(), for which IndexOfTopLevelItem() yields no usable index.
        The per-item Selected property is more reliable and cannot accumulate
        stale clicks.
        """
        found = []
        for ix in displayed:
            item = entry_map.get(ix)
            if item is None:
                continue
            try:
                if bool(item.Selected):
                    found.append(ix)
            except Exception:
                pass
        if found:
            return found
        # Fallback for UIManager builds that expose SelectedItems() only.
        try:
            selected = tree.SelectedItems()
            for position in range(tree.TopLevelItemCount()):
                item = tree.TopLevelItem(position)
                if any(item == chosen for chosen in selected):
                    if 0 <= position < len(displayed):
                        found.append(displayed[position])
        except Exception as error:
            print("Media Auto Relink: selection inspection failed:", error)
        return found

    def refresh():
        exact = sum(row["status"] == "ready" for row in rows)
        review = sum(row["status"] in ("suggested_review", "located_review") for row in rows)
        other = len(rows) - exact - review
        widgets["Summary"].Text = "%d exact  |  %d need approval  |  %d unavailable / other  |  %d files" % (
            exact, review, other, len(rows))
        approved = sum(v == "confirm" for v in decisions.values())
        manual = sum(v == "skip" for v in decisions.values())
        widgets["Staged"].Text = "%d approved  |  %d left for manual relinking  |  no changes until Apply" % (
            approved, manual)
        # Updating decisions should not erase highlighted table selections.
        for index, entry in entry_map.items():
            entry.Text[0] = decision_label(index)

    def update_choice(choice):
        indices = selected_indices()
        if not indices:
            widgets["Details"].Text = "Select file rows first, or use the Show filter and Approve Shown Matches."
            return
        rejected = 0
        for index in indices:
            row = rows[index]
            if choice == "confirm" and row["status"] not in ("ready", "suggested_review", "located_review"):
                rejected += 1
                continue
            if choice == "reset":
                decisions.pop(index, None)
            else:
                decisions[index] = choice
        refresh()
        if rejected:
            widgets["Details"].Text = ("%d selected files have no verified local path and cannot be approved. "
                                       "They will remain untouched." % rejected)

    def on_select(event):
        indices = selected_indices()
        if not indices:
            widgets["Details"].Text = "0 highlighted files. Click a table row to select it."
            return
        if len(indices) > 1:
            widgets["Details"].Text = "%d highlighted files. Actions affect only these highlighted rows." % len(indices)
        else:
            row = rows[indices[0]]
            widgets["Details"].Text = ("Original: " + str(row.get("original") or "(unavailable)") +
                "\\nLocal: " + str(row.get("expected") or "(no candidate; manual relink needed)") +
                "\\nReason: " + match_label(row))

    def on_confirm(event):
        update_choice("confirm")

    def on_skip(event):
        update_choice("skip")

    def on_reset(event):
        update_choice("reset")

    def on_filter(event):
        fill_table()

    def on_header(event):
        try:
            column = event.get("index", event.get("column")) if isinstance(event, dict) else None
            column = int(column)
        except (ValueError, TypeError):
            return
        if not 0 <= column <= 4:
            return
        if sorting["column"] == column:
            sorting["descending"] = not sorting["descending"]
        else:
            sorting["column"] = column
            sorting["descending"] = False
        fill_table()


    def on_approve_visible(event):
        for index in list(displayed):
            if rows[index]["status"] in ("ready", "suggested_review", "located_review"):
                decisions[index] = "confirm"
        refresh()

    def on_locate(event):
        chosen = selected_indices()
        targets = chosen if chosen else [
            ix for ix in displayed
            if rows[ix]["status"] not in ("ready", "already_online", "suggested_review", "located_review", "original_path_unavailable")
        ]
        if not targets:
            widgets["Details"].Text = "Select missing files or choose Show: Not found / other."
            return
        folder = fusion.RequestDir()
        if not folder:
            return
        root = Path(str(folder)).expanduser()
        if not root.is_dir():
            widgets["Details"].Text = "Selected folder is unavailable."
            return
        needed = {str(rows[ix]["name"]).casefold() for ix in targets}
        matches = {}
        try:
            for current, dirs, files in os.walk(str(root), followlinks=False):
                for filename in files:
                    key = filename.casefold()
                    if key in needed:
                        matches.setdefault(key, []).append(Path(current) / filename)
        except OSError as error:
            widgets["Details"].Text = "Unable to search selected folder: " + str(error)
            return
        matched, ambiguous = 0, 0
        for ix in targets:
            row = rows[ix]
            if row["status"] in ("ready", "already_online", "suggested_review", "located_review", "original_path_unavailable"):
                continue
            candidates = matches.get(str(row["name"]).casefold(), [])
            if len(candidates) == 1:
                row["expected"] = str(candidates[0])
                row["status"] = "located_review"
                row["warning"] = "Found by filename in selected folder. Approval required."
                decisions.pop(ix, None)
                matched += 1
            elif len(candidates) > 1:
                row["status"] = "multiple_candidates"
                row["warning"] = "Multiple files share this filename. No automatic choice made."
                ambiguous += 1
        fill_table()
        refresh()
        widgets["Details"].Text = "%d found; %d ambiguous. Review paths before approval." % (matched, ambiguous)

    def on_clear_visible(event):
        for index in list(displayed):
            decisions.pop(index, None)
        refresh()
        widgets["Details"].Text = "Decisions cleared for all currently shown files. No media was changed."

    def on_exact(event):
        for idx, row in enumerate(rows):
            if row["status"] == "ready":
                decisions[idx] = "confirm"
        refresh()

    outcome = {"approved": None}

    def on_apply(event):
        outcome["approved"] = sorted(idx for idx, choice in decisions.items() if choice == "confirm")
        dispatcher.ExitLoop()

    def on_cancel(event):
        dispatcher.ExitLoop()

    win.On.Filter.CurrentIndexChanged = on_filter
    win.On.Matches.HeaderSectionClicked = on_header
    win.On.ApproveVisible.Clicked = on_approve_visible
    win.On.ClearVisible.Clicked = on_clear_visible
    win.On.Locate.Clicked = on_locate
    win.On.Matches.ItemClicked = on_select
    win.On.Matches.ItemSelectionChanged = on_select
    win.On.Confirm.Clicked = on_confirm
    win.On.Skip.Clicked = on_skip
    win.On.Reset.Clicked = on_reset
    win.On.ConfirmExact.Clicked = on_exact
    win.On.Apply.Clicked = on_apply
    win.On.CloseButton.Clicked = on_cancel
    win.On.MARReview.Close = on_cancel
    fill_table()
    refresh()
    win.Show()
    dispatcher.RunLoop()
    win.Hide()
    return outcome["approved"]
