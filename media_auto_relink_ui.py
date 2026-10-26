"""Native Fusion UI review dialog for Media Auto Relink."""
def review_window(fusion, rows, workspace):
    """Return approved row indices, or None if cancelled.

    All changes are staged. No relinking happens inside the dialog.
    """
    ui = fusion.UIManager
    dispatcher = __import__("bmd").UIDispatcher(ui)
    win = dispatcher.AddWindow(
        {"ID": "MARReview", "WindowTitle": "Media Auto Relink — Review",
         "Geometry": [100, 100, 1120, 680], "MinimumSize": [780, 460]},
        ui.VGroup([
            ui.HGroup([
                ui.Label({"ID": "WorkspaceLabel", "Text": "Workspace: " + str(workspace), "Weight": 1}),
                ui.Button({"ID": "CloseButton", "Text": "Cancel"})
            ]),
            ui.Label({"ID": "Summary", "Text": "Review matches before applying."}),
            ui.Tree({"ID": "Matches", "Weight": 1, "SortingEnabled": False,
                     "AlternatingRowColors": True}),
            ui.Label({"ID": "Details", "Text": "Select a row to inspect its original and proposed paths.", "WordWrap": True}),
            ui.HGroup([
                ui.Button({"ID": "Confirm", "Text": "Confirm Selected"}),
                ui.Button({"ID": "Skip", "Text": "Skip Selected"}),
                ui.Button({"ID": "ConfirmExact", "Text": "Confirm All Exact"}),
                ui.Button({"ID": "Reset", "Text": "Reset Selected"})
            ]),
            ui.HGroup([
                ui.Label({"ID": "Staged", "Text": "No changes applied.", "Weight": 1}),
                ui.Button({"ID": "Apply", "Text": "Apply Confirmed Relinks"})
            ])
        ])
    )
    items = win.GetItems()
    tree = items["Matches"]
    tree.SetHeaderLabels(["Choice", "Status", "Clip", "Original path", "Proposed path"])
    try:
        tree.SetColumnWidth(0, 105)
        tree.SetColumnWidth(1, 160)
        tree.SetColumnWidth(2, 190)
        tree.SetColumnWidth(3, 300)
        tree.SetColumnWidth(4, 300)
    except Exception:
        pass
    choices = {}
    indexed = {}
    for index, row in enumerate(rows):
        entry = tree.NewItem()
        entry.Text[0] = "Pending"
        entry.Text[1] = row["status"]
        entry.Text[2] = row["name"]
        entry.Text[3] = row.get("original") or ""
        entry.Text[4] = row.get("expected") or ""
        if row["status"] == "ready":
            entry.Text[0] = "Exact"
        elif row["status"] in ("already_online",):
            entry.Text[0] = "Online"
        else:
            entry.Text[0] = "Unresolved"
        tree.AddTopLevelItem(entry)
        indexed[index] = entry

    def selected_index():
        try:
            selected = tree.SelectedItems()
            if not selected:
                return None
            choice = selected[0]
            for ix, obj in indexed.items():
                if obj is choice:
                    return ix
            # UIManager may proxy TreeItems; index lookup is also supported.
            return tree.IndexOfTopLevelItem(choice)
        except Exception:
            return None

    def summary():
        approved = sum(1 for v in choices.values() if v == "confirm")
        skipped = sum(1 for v in choices.values() if v == "skip")
        eligible = sum(1 for row in rows if row["status"] == "ready")
        items["Summary"].Text = "%d exact paths available  •  %d other entries  •  %d total" % (
            eligible, len(rows) - eligible, len(rows))
        items["Staged"].Text = "%d confirmed  •  %d skipped  •  nothing applied yet" % (approved, skipped)

    def update(ix, choice):
        if ix is None or ix not in indexed:
            return
        row = rows[ix]
        # Do not offer approval when an exact target does not exist.
        if choice == "confirm" and row["status"] != "ready":
            items["Details"].Text = ("Cannot confirm this entry: no verified target path. "
                                     "Relink it manually or correct its folder structure.\n"
                                     + str(row.get("original") or ""))
            return
        choices[ix] = choice
        indexed[ix].Text[0] = "Confirmed" if choice == "confirm" else "Skipped" if choice == "skip" else "Pending"
        summary()

    def on_select(ev):
        ix = selected_index()
        if ix is not None and ix in range(len(rows)):
            row = rows[ix]
            items["Details"].Text = ("Original: " + str(row.get("original") or "(unavailable)") +
                                     "\nExpected: " + str(row.get("expected") or "(no safe match)") +
                                     "\nStatus: " + row["status"])

    def on_confirm(ev):
        update(selected_index(), "confirm")

    def on_skip(ev):
        update(selected_index(), "skip")

    def on_reset(ev):
        update(selected_index(), "reset")

    def on_exact(ev):
        for ix, row in enumerate(rows):
            if row["status"] == "ready":
                update(ix, "confirm")

    result = {"approved": None}
    def on_apply(ev):
        result["approved"] = [ix for ix, val in choices.items() if val == "confirm"]
        dispatcher.ExitLoop()

    def on_cancel(ev):
        dispatcher.ExitLoop()

    win.On.Matches.ItemClicked = on_select
    win.On.Confirm.Clicked = on_confirm
    win.On.Skip.Clicked = on_skip
    win.On.Reset.Clicked = on_reset
    win.On.ConfirmExact.Clicked = on_exact
    win.On.Apply.Clicked = on_apply
    win.On.CloseButton.Clicked = on_cancel
    win.On.MARReview.Close = on_cancel
    summary()
    win.Show()
    dispatcher.RunLoop()
    win.Hide()
    return result["approved"]
