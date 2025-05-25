import customtkinter as ctk
import json
import os
import re
from tkinter import messagebox
import csv
from tkinter import filedialog, messagebox
from tag_import_utils import parse_productivity_csv
from tag_import_dialog import import_tags_from_csv_gui
from tkinter import ttk



class TagConfiguratorTab(ctk.CTkFrame):
    """
    Tab for configuring PLC tags, including adding, editing, removing, and validating tags.
    Provides real-time duplicate name validation and in-place editing.
    """
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.tags = []
        self.unsaved_changes = False
        self.selected_tag_index = None
        self.create_widgets()
        self.load_tags()

    def create_widgets(self):
        tooltip_font = ("Arial", 10, "italic")
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(padx=10, pady=10, fill="x")

        self.name_var = ctk.StringVar()
        self.name_entry = ctk.CTkEntry(form_frame, placeholder_text="Tag Name", textvariable=self.name_var)
        self.name_entry_tooltip = ctk.CTkLabel(form_frame, text="Enter a unique name for the tag", font=tooltip_font, text_color="gray")
        self.name_entry.grid(row=0, column=0, padx=5, pady=5)
        self.name_entry_tooltip.grid(row=1, column=0, padx=5, pady=(0, 10))

        self.name_entry.bind("<FocusOut>", self.on_name_entry_focus_out)
        self.name_var.trace_add("write", self.on_name_entry_change)

        self.address_entry = ctk.CTkEntry(form_frame, placeholder_text="Address")
        self.address_entry_tooltip = ctk.CTkLabel(form_frame, text="Integer address (e.g., 0, 1, 100)", font=tooltip_font, text_color="gray")
        self.address_entry.grid(row=0, column=1, padx=5, pady=5)
        self.address_entry_tooltip.grid(row=1, column=1, padx=5, pady=(0, 10))

        self.type_option = ctk.CTkOptionMenu(form_frame, values=["Coil", "Register"])
        self.type_option.set("Coil")
        # Improved tooltip
        self.type_option_tooltip = ctk.CTkLabel(form_frame, text="Select Modbus data type (Coil or Register)", font=tooltip_font, text_color="gray")
        self.type_option.grid(row=0, column=2, padx=5, pady=5)
        self.type_option_tooltip.grid(row=1, column=2, padx=5, pady=(0, 10))

        self.enabled_var = ctk.BooleanVar(value=True)
        self.enabled_checkbox = ctk.CTkCheckBox(form_frame, text="Enabled", variable=self.enabled_var)
        self.enabled_checkbox_tooltip = ctk.CTkLabel(form_frame, text="Uncheck to disable tag without deleting", font=tooltip_font, text_color="gray")
        self.enabled_checkbox.grid(row=0, column=3, padx=5, pady=5)
        self.enabled_checkbox_tooltip.grid(row=1, column=3, padx=5, pady=(0, 10))

        button_frame = ctk.CTkFrame(self)
        button_frame.pack(padx=10, pady=(0, 10), fill="x")

        self.add_button = ctk.CTkButton(button_frame, text="Add Tag", command=self.add_tag)
        self.add_button.pack(side="left", padx=5)

        self.edit_button = ctk.CTkButton(button_frame, text="Edit Tag", command=self.edit_tag)
        self.edit_button.pack(side="left", padx=5)

        self.remove_button = ctk.CTkButton(button_frame, text="Remove Tag", command=self.remove_tag)
        self.remove_button.pack(side="left", padx=5)

        self.save_button = ctk.CTkButton(button_frame, text="Save Tags", command=self.save_tags)
        self.save_button.pack(side="left", padx=5)

        # Add "Import Tags from CSV" button
        self.import_button = ctk.CTkButton(
            button_frame,
            text="Import Tags from CSV",
            command=self.import_tags_from_csv)  # We will define this method next
        self.import_button.pack(side="left", padx=5)


        #self.tag_display = ctk.CTkTextbox(self, width=800, height=200)
        #self.tag_display.pack(padx=10, pady=10, fill="both", expand=True)
        #self.tag_display.bind("<Button-1>", self.on_tag_display_click)
        #self.tag_display.configure(state="disabled")

        self.tree = ttk.Treeview(self, columns=("Name", "Type", "Address", "Enabled"), show="headings", height=8)

        self.tree.heading("Name", text="Name")
        self.tree.heading("Type", text="Type")
        self.tree.heading("Address", text="Address")
        self.tree.heading("Enabled", text="Enabled")

        self.tree.column("Name", width=200)
        self.tree.column("Type", width=100, anchor="center")
        self.tree.column("Address", width=100, anchor="center")
        self.tree.column("Enabled", width=100, anchor="center")

        self.tree.pack(padx=10, pady=10, fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)


    def import_tags_from_csv(self):
        import_tags_from_csv_gui(
            self.tags,
            update_callback=lambda: (
            self.update_tag_display(),
            setattr(self, "unsaved_changes", True),
            self.save_button.configure(fg_color="#FFA500")),
            app_stop_start=lambda: (self.app.stop_logging(), self.app.start_logging())
        )

    def clean_tag_name(self, name):
        """
        Strips whitespace and normalizes spaces in tag name.
        """
        name = name.strip()
        name = re.sub(r'\s+', ' ', name)
        return name

    def update_tag_display(self, highlight_index=None):
        # Clear the tree
        for row in self.tree.get_children():
            self.tree.delete(row)

        for idx, tag in enumerate(self.tags):
            values = (
                tag["name"],
                tag["type"],
                tag["address"],
                "Yes" if tag.get("enabled", True) else "No"
            )

            tag_id = self.tree.insert("", "end", iid=str(idx), text=tag["name"], values=values)
            if idx == highlight_index:
                self.tree.selection_set(tag_id)
                self.tree.see(tag_id)


    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        tag = self.tags[idx]
        self.name_var.set(tag['name'])
        self.address_entry.delete(0, "end")
        self.address_entry.insert(0, str(tag['address']))
        self.type_option.set(tag['type'])
        self.enabled_var.set(tag.get("enabled", True))
        self.selected_tag_index = idx

    def get_selected_tag_index_from_cursor(self, event):
        """
        Determines which tag is clicked in the display.
        """
        # Get the mouse y position in the widget and calculate the corresponding line index
        try:
            index = self.tag_display.index(f"@{event.x},{event.y}")
            line_num = int(index.split(".")[0]) - 1
            if 0 <= line_num < len(self.tags):
                return line_num
        except Exception:
            pass
        return None

    def on_tag_display_click(self, event):
        """
        When a tag is clicked in the display, populate the fields with that tag's info.
        """
        idx = self.get_selected_tag_index_from_cursor(event)
        if idx is not None:
            print(f"[DEBUG] Selected tag index: {idx}")  # Add this
            tag = self.tags[idx]
            self.name_var.set(tag['name'])
            self.address_entry.delete(0, "end")
            self.address_entry.insert(0, str(tag['address']))
            self.type_option.set(tag['type'])
            self.enabled_var.set(tag.get("enabled", True))
            self.selected_tag_index = idx

    def add_tag(self):
        """
        Adds a tag after checking for duplicate name and duplicate address/type.
        Provides immediate feedback for errors.
        """
        name = self.clean_tag_name(self.name_entry.get())
        try:
            address = int(self.address_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Address", "Address must be an integer.")
            return
        tag_type = self.type_option.get()
        enabled = self.enabled_var.get()

        if not name:
            messagebox.showerror("Missing Name", "Please enter a tag name.")
            return

        # Check for duplicate address/type combo
        for tag in self.tags:
            if tag["address"] == address and tag["type"] == tag_type:
                messagebox.showerror("Duplicate Address", f"Another tag already uses address {address} as a {tag_type}.")
                return

        # Check for duplicate name (case-insensitive)
        for tag in self.tags:
            if self.clean_tag_name(tag["name"]).lower() == name.lower():
                messagebox.showerror("Duplicate Name", f"Another tag already uses the name '{name}'.")
                self.name_entry_tooltip.configure(
                    text=f"Name '{name}' already exists!",
                    text_color="red"
                )
                if hasattr(self.name_entry, 'configure'):
                    try:
                        self.name_entry.configure(border_color="red")
                    except Exception:
                        pass
                return

        self.name_entry_tooltip.configure(
            text="Enter a unique name for the tag",
            text_color="gray"
        )
        if hasattr(self.name_entry, 'configure'):
            try:
                self.name_entry.configure(border_color="gray")
            except Exception:
                pass

        self.tags.append({"name": name, "address": address, "type": tag_type, "enabled": enabled})
        self.unsaved_changes = True
        self.save_button.configure(fg_color="#FFA500")
        self.update_tag_display()
        self.selected_tag_index = None

    def edit_tag(self):
        if self.selected_tag_index is None or not (0 <= self.selected_tag_index < len(self.tags)):
            messagebox.showerror("No Tag Selected", "Please select a tag to edit by clicking a line in the tag display.")
            return

        name = self.clean_tag_name(self.name_entry.get())
        try:
            address = int(self.address_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Address", "Address must be an integer.")
            return

        tag_type = self.type_option.get()
        enabled = self.enabled_var.get()

        # Check for duplicate name (ignore self)
        for idx, tag in enumerate(self.tags):
            if idx != self.selected_tag_index and self.clean_tag_name(tag["name"]).lower() == name.lower():
                messagebox.showerror("Duplicate Name", f"Another tag already uses the name '{name}'.")
                self.name_entry_tooltip.configure(
                    text=f"Name '{name}' already exists!",
                    text_color="red"
                )
                try:
                    self.name_entry.configure(border_color="red")
                except Exception:
                    pass
                return

        # Check for duplicate address/type combo (ignore self)
        for idx, tag in enumerate(self.tags):
            if idx != self.selected_tag_index and tag["address"] == address and tag["type"] == tag_type:
                messagebox.showerror("Duplicate Address", f"Another tag already uses address {address} as a {tag_type}.")
                return

        # Clear tooltip if valid
        self.name_entry_tooltip.configure(
            text="Enter a unique name for the tag",
            text_color="gray"
        )
        try:
            self.name_entry.configure(border_color="gray")
        except Exception:
            pass

        # ✅ Update the tag
        updated_tag = {
            "name": name,
            "address": address,
            "type": tag_type,
            "enabled": enabled
        }

        self.tags[self.selected_tag_index] = updated_tag
        print(f"[DEBUG] Updated tag at index {self.selected_tag_index}: {updated_tag}")

        self.unsaved_changes = True
        self.save_button.configure(fg_color="#FFA500")
        self.update_tag_display()
        self.app.tags = self.tags.copy()

        updated_tag = self.tags[self.selected_tag_index]
        self.name_var.set(updated_tag['name'])
        self.address_entry.delete(0, "end")
        self.address_entry.insert(0, str(updated_tag['address']))
        self.type_option.set(updated_tag['type'])
        self.enabled_var.set(updated_tag.get("enabled", True))
        # Leave selection intact




    def on_name_entry_focus_out(self, event=None):
        """
        Checks for duplicate tag names when the name entry loses focus.
        Updates tooltip and border color as needed.
        """
        name = self.clean_tag_name(self.name_entry.get())
        if not name:
            self.name_entry_tooltip.configure(
                text="Enter a unique name for the tag",
                text_color="gray"
            )
            if hasattr(self.name_entry, 'configure'):
                try:
                    self.name_entry.configure(border_color="gray")
                except Exception:
                    pass
            return
        count = sum(1 for tag in self.tags if self.clean_tag_name(tag["name"]).lower() == name.lower())
        if count > 0:
            self.name_entry_tooltip.configure(
                text=f"Name '{name}' already exists!",
                text_color="red"
            )
            if hasattr(self.name_entry, 'configure'):
                try:
                    self.name_entry.configure(border_color="red")
                except Exception:
                    pass
        else:
            self.name_entry_tooltip.configure(
                text="Enter a unique name for the tag",
                text_color="gray"
            )
            if hasattr(self.name_entry, 'configure'):
                try:
                    self.name_entry.configure(border_color="gray")
                except Exception:
                    pass

    def on_name_entry_change(self, *args):
        """
        Reuse focus-out duplicate check on text change.
        """
        self.on_name_entry_focus_out()

    def save_tags(self):
        """
        Saves all tags to the config file after checking for duplicates.
        """
        seen = {}
        duplicates = []
        name_set = set()

        for tag in self.tags:
            key = (tag['type'], tag['address'])
            name_lower = self.clean_tag_name(tag['name']).lower()
            if key in seen:
                duplicates.append((tag['name'], seen[key], key[0], key[1]))
            else:
                seen[key] = tag['name']
            if name_lower in name_set:
                messagebox.showerror("Duplicate Names", f"Multiple tags share the name '{tag['name']}'.")
                return
            name_set.add(name_lower)

        if duplicates:
            conflict_text = "\n".join([f"{a} and {b} share {t} @ {addr}" for a, b, t, addr in duplicates])
            messagebox.showerror("Duplicate Tags", f"Cannot save due to duplicates:\n{conflict_text}")
            return

        path = "plc_logger_config.json"
        try:
            # Read the existing config, update only the tags section
            if os.path.exists(path):
                with open(path, "r") as f:
                    config = json.load(f)
            else:
                config = {}
            config["tags"] = self.tags
            with open(path, "w") as f:
                json.dump(config, f, indent=4)
            messagebox.showinfo("Saved", f"Tags saved to {path}")
            self.app.tags = self.tags.copy()
            self.unsaved_changes = False
            self.save_button.configure(
                fg_color=("#1f6aa5", "#144870"),
                hover_color=("#1786c6", "#1a5e89")
            )
            self.app.update_tag_filter_dropdown()
        except Exception as e:
            messagebox.showerror("Error Saving", str(e))

    def remove_tag(self):
        """
        Removes a tag matching name, address, and type.
        """
        name = self.clean_tag_name(self.name_entry.get())
        address = self.address_entry.get().strip()
        tag_type = self.type_option.get()

        tag_found = None
        for tag in self.tags:
            if (
                self.clean_tag_name(tag["name"]).lower() == name.lower() and
                str(tag["address"]) == address and
                tag["type"] == tag_type
            ):
                tag_found = tag
                break

        if tag_found:
            confirm = messagebox.askyesno(
                "Confirm Deletion",
                f"Remove tag: {tag_found['name']} [{tag_found['type']} @ {tag_found['address']}]?"
            )
            if confirm:
                self.tags.remove(tag_found)
                self.unsaved_changes = True
                self.save_button.configure(fg_color="#FFA500")
                self.update_tag_display()
        else:
            messagebox.showinfo("Not Found", "No matching tag found to remove.")

    def load_tags(self):
        """
        Loads tags from config file and updates the display.
        """
        path = "plc_logger_config.json"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    config = json.load(f)
                    self.tags = config.get("tags", [])
                self.update_tag_display()
            except Exception as e:
                messagebox.showerror("Error Loading", str(e))
