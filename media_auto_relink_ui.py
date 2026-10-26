"""Compact native Fusion UI review for Media Auto Relink.

All choices are staged. Apply only passes explicitly approved indices to caller.
"""

def review_window(fusion, bmd, rows, workspace):
    ui = fusion.UIManager
    dispatcher = bmd.UIDispatcher(ui)
    win = dispatcher.AddWindow(
        {"ID": "MARReview", "WindowTitle": "Media Auto Relink — Review",
         "Geometry": [100, 100, 1200, 720], "MinimumSize": [850, 540]},
        ui.VGroup({"Spacing": 6, "Margin": 10}, [
            ui.HGroup({"Weight": 0, "Spacing": 8}, [
                ui.Label({"ID": "WorkspaceLabel", "Text": "Workspace: " + str(workspace), "Weight": 1}),
                ui.Button({"ID": "CloseButton", "Text": "Cancel", "MaximumSize": [90, 30]})
            ]),
            ui.Label({"ID": "Summary", "Text": "", "Weight": 0, "MaximumSize": [1100, 28]}),
            ui.Label({"ID": "Hint", "Text": "Select one or more rows (Cmd-click / Shift-click), then Approve or Leave for manual relinking.",
                      "Weight": 0, "MaximumSize": [1100, 25]}),
            ui.Tree({"ID": "Matches", "Weight": 1, "SelectionMode": "ExtendedSelection",
                     "SortingEnabled": False, "AlternatingRowColors": True}),
            ui.Label({"ID": "Details", "Text": "Click a file to inspect both paths.", "Weight": 0,
                      "WordWrap": True, "MinimumSize": [200, 60], "MaximumSize": [1100, 95]}),
            ui.HGroup({"Weight": 0, "Spacing": 8}, [
                ui.Button({"ID": "Confirm", "Text": "Approve Selection", "MaximumSize": [160, 32]}),
                ui.Button({"ID": "Skip", "Text": "Leave for Manual", "MaximumSize": [160, 32]}),
                ui.Button({"ID": "ConfirmExact", "Text": "Approve All Exact", "MaximumSize": [160, 32]}),
                ui.Button({"ID": "Reset", "Text": "Clear Selection Choices", "MaximumSize": [185, 32]}),
                ui.Label({"ID": "ToolbarSpacer", "Text": "", "Weight": 1})
            ]),
            ui.HGroup({"Weight": 0, "Spacing": 8}, [
                ui.Label({"ID": "Staged", "Text": "", "Weight": 1}),
                ui.Button({"ID": "Apply", "Text": "Apply Approved Only", "MaximumSize": [185, 34]})
            ])
        ])
    )
    widgets = win.GetItems()
    tree = widgets["Matches"]
    tree.SetHeaderLabels(["Decision", "Match", "Filename", "Original path", "Suggested local path"])
    for column, width in enumerate([125, 155, 195, 300, 350]):
        try:
            tree.SetColumnWidth(column, width)
        except Exception:
            pass

    def match_label(row):
        return {
            "ready": "Exact path",
            "suggested_review": "Folder differs — review",
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
        if rows[index]["status"] == "suggested_review":
            return "Needs review"
        if rows[index]["status"] == "already_online":
            return "Online"
        return "Not found"

    decisions = {}
    entries = []
    for index, row in enumerate(rows):
        entry = tree.NewItem()
        entry.Text[0] = decision_label(index)
        entry.Text[1] = match_label(row)
        entry.Text[2] = str(row["name"])
        entry.Text[3] = str(row.get("original") or "")
        entry.Text[4] = str(row.get("expected") or "")
        tree.AddTopLevelItem(entry)
        entries.append(entry)

    def selected_indices():
        indices = []
        try:
            selected = tree.SelectedItems() or []
            for item in selected:
                idx = tree.IndexOfTopLevelItem(item)
                if isinstance(idx, int) and 0 <= idx < len(rows) and idx not in indices:
                    indices.append(idx)
        except Exception as error:
            print("Unable to read table selection:", error)
        return indices

    def refresh():
        exact = sum(row["status"] == "ready" for row in rows)
        review = sum(row["status"] == "suggested_review" for row in rows)
        other = len(rows) - exact - review
        widgets["Summary"].Text = "%d exact  |  %d need approval  |  %d unavailable / other  |  %d files" % (
            exact, review, other, len(rows))
        approved = sum(v == "confirm" for v in decisions.values())
        manual = sum(v == "skip" for v in decisions.values())
        widgets["Staged"].Text = "%d approved  |  %d left for manual relinking  |  no changes until Apply" % (
            approved, manual)
        for index, entry in enumerate(entries):
            entry.Text[0] = decision_label(index)

    def update_choice(choice):
        indices = selected_indices()
        if not indices:
            widgets["Details"].Text = "Select one or more file rows first. Use Cmd-click or Shift-click on macOS."
            return
        rejected = 0
        for index in indices:
            row = rows[index]
            if choice == "confirm" and row["status"] not in ("ready", "suggested_review"):
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
            return
        if len(indices) > 1:
            widgets["Details"].Text = "%d files selected. Approve or leave these files for manual relinking." % len(indices)
        else:
            row = rows[indices[0]]
            widgets["Details"].Text = ("Original: " + str(row.get("original") or "(unavailable)") +
                "\nLocal: " + str(row.get("expected") or "(no candidate; manual relink needed)") +
                "\nReason: " + match_label(row))

    def on_confirm(event):
        update_choice("confirm")

    def on_skip(event):
        update_choice("skip")

    def on_reset(event):
        update_choice("reset")

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

    win.On.Matches.ItemClicked = on_select
    win.On.Matches.ItemSelectionChanged = on_select
    win.On.Confirm.Clicked = on_confirm
    win.On.Skip.Clicked = on_skip
    win.On.Reset.Clicked = on_reset
    win.On.ConfirmExact.Clicked = on_exact
    win.On.Apply.Clicked = on_apply
    win.On.CloseButton.Clicked = on_cancel
    win.On.MARReview.Close = on_cancel
    refresh()
    win.Show()
    dispatcher.RunLoop()
    win.Hide()
    return outcome["approved"]
