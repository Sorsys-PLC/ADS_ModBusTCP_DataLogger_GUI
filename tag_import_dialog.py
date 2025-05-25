# tag_import_dialog.py

from tkinter import filedialog, messagebox, Toplevel, Label, Button
from tag_import_utils import parse_productivity_csv

def show_duplicate_dialog(conflict_name, new_name, addr, tag_type):
    choice = {"value": None}
    win = Toplevel()
    win.title("Duplicate Tag")
    win.grab_set()
    Label(win, text=(
        f"Duplicate tag at {tag_type} address {addr} already exists as '{conflict_name}'.\n"
        f"Do you want to overwrite it with '{new_name}'?\n\n"
        "Choose an option below:"
    )).pack(padx=20, pady=10)

    def set_choice(val):
        choice["value"] = val
        win.destroy()

    Button(win, text="Overwrite This", command=lambda: set_choice("overwrite")).pack(fill='x')
    Button(win, text="Skip This", command=lambda: set_choice("skip")).pack(fill='x')
    Button(win, text="Overwrite All", command=lambda: set_choice("overwrite_all")).pack(fill='x')
    Button(win, text="Skip All", command=lambda: set_choice("skip_all")).pack(fill='x')

    win.wait_window()
    return choice["value"]

def import_tags_from_csv_gui(tag_list, update_callback, app_stop_start):
    file_path = filedialog.askopenfilename(
        title="Select Tag CSV",
        filetypes=[("CSV Files", "*.csv")]
    )
    if not file_path:
        return

    new_tags, duplicates, result = parse_productivity_csv(file_path, tag_list)

    if new_tags is None:
        messagebox.showerror("Import Error", f"Failed to read CSV: {duplicates}")
        return

    overwrite_all = False
    skip_all = False
    actually_imported = 0

    tag_list.extend(new_tags)
    actually_imported += len(new_tags)

    for dup in duplicates:
        addr = dup["address"]
        ttype = dup["type"]
        name = dup["name"]

        conflict = next(
            (t for t in tag_list if t["address"] == addr and t["type"].lower() == ttype.lower()),
            None
        )

        if skip_all:
            continue

        if not overwrite_all:
            action = show_duplicate_dialog(conflict["name"], name, addr, ttype)
            if action == "overwrite":
                tag_list.remove(conflict)
                tag_list.append(dup)
                actually_imported += 1
            elif action == "skip":
                continue
            elif action == "overwrite_all":
                overwrite_all = True
                tag_list.remove(conflict)
                tag_list.append(dup)
                actually_imported += 1
            elif action == "skip_all":
                skip_all = True
                continue
        else:
            tag_list.remove(conflict)
            tag_list.append(dup)
            actually_imported += 1

    if actually_imported:
        update_callback()
        app_stop_start()

        summary = f"Imported {actually_imported} tag(s). Logger restarted.\n"
        summary += "Changes are not saved until you click 'Save Tags'."
    else:
        summary = "No new tags were imported."

    skipped = result["skipped_no_address"] + result["skipped_unsupported"]
    if skipped:
        details = []
        if result["skipped_no_address"]:
            details.append(f"{result['skipped_no_address']} with no address")
        if result["skipped_unsupported"]:
            details.append(f"{result['skipped_unsupported']} unsupported type")
        summary += f"\nSkipped {skipped} tag(s): " + ", ".join(details)

    messagebox.showinfo("Import Result", summary)
