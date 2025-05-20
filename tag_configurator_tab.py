import customtkinter as ctk
import json
import os
from tkinter import messagebox

class TagConfiguratorTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.tags = []
        self.unsaved_changes = False
        self.create_widgets()
        self.load_tags()

    def create_widgets(self):
        self.name_entry = ctk.CTkEntry(self, placeholder_text="Tag Name")
        self.name_entry.grid(row=0, column=0, padx=10, pady=10)

        self.address_entry = ctk.CTkEntry(self, placeholder_text="Address")
        self.address_entry.grid(row=0, column=1, padx=10, pady=10)

        self.type_option = ctk.CTkOptionMenu(self, values=["Coil", "Register"])
        self.type_option.grid(row=0, column=2, padx=10, pady=10)
        self.type_option.set("Coil")

        self.enabled_var = ctk.BooleanVar(value=True)
        self.enabled_checkbox = ctk.CTkCheckBox(self, text="Enabled", variable=self.enabled_var)
        self.enabled_checkbox.grid(row=0, column=3, padx=10, pady=10)

        self.add_button = ctk.CTkButton(self, text="Add Tag", command=self.add_tag)
        self.add_button.grid(row=1, column=0, padx=10, pady=10)

        self.remove_button = ctk.CTkButton(self, text="Remove Tag", command=self.remove_tag)
        self.remove_button.grid(row=1, column=1, padx=10, pady=10)

        self.save_button = ctk.CTkButton(self, text="Save Tags", command=self.save_tags)
        self.save_button.grid(row=1, column=2, padx=10, pady=10)

        self.tag_display = ctk.CTkTextbox(self, width=800, height=200)
        self.tag_display.grid(row=2, column=0, columnspan=7, padx=10, pady=10)

    def add_tag(self):
        name = self.name_entry.get().strip()
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

        for tag in self.tags:
            if tag["type"] == tag_type and tag["address"] == address:
                messagebox.showerror("Duplicate Tag", f"Another tag already uses {tag_type} @ {address}.")
                return
            if tag["name"].strip().lower() == name.lower():
                messagebox.showerror("Duplicate Name", f"A tag with the name '{name}' already exists.")
                return

        self.tags.append({"name": name, "address": address, "type": tag_type, "enabled": enabled})
        self.unsaved_changes = True
        self.save_button.configure(fg_color='orange')
        self.update_tag_display()

    def remove_tag(self):
        name = self.name_entry.get().strip()
        address = self.address_entry.get().strip()
        tag_type = self.type_option.get()

        tag_found = None
        for tag in self.tags:
            if (
                tag["name"].strip().lower() == name.lower() and
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
                self.save_button.configure(fg_color='orange')
                self.update_tag_display()
        else:
            messagebox.showinfo("Not Found", "No matching tag found to remove.")

    def update_tag_display(self):
        self.tag_display.delete("1.0", "end")
        seen = {}
        for tag in self.tags:
            key = (tag['type'], tag['address'])
            enabled_status = "Enabled" if tag.get("enabled", True) else "Disabled"
            label = f"{tag['name']} [{tag['type']} @ {tag['address']}] ({enabled_status})"
            if key in seen:
                self.tag_display.insert("end", f"{label}  <-- DUPLICATE\n")
            else:
                self.tag_display.insert("end", f"{label}\n")
                seen[key] = tag['name']
        self.tag_display.see("end")

    def save_tags(self):
        seen = {}
        duplicates = []
        name_set = set()
        for tag in self.tags:
            key = (tag['type'], tag['address'])
            name_lower = tag['name'].strip().lower()
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

        path = "plc_tag_config.json"
        try:
            with open(path, "w") as f:
                json.dump(self.tags, f, indent=4)
            messagebox.showinfo("Saved", f"Tags saved to {path}")
            self.app.tags = self.tags.copy()
            self.unsaved_changes = False
            self.save_button.configure(fg_color=ctk.ThemeManager.theme['CTkButton']['fg_color'])
            self.app.update_tag_filter_dropdown()
        except Exception as e:
            messagebox.showerror("Error Saving", str(e))

    def load_tags(self):
        path = "plc_tag_config.json"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    self.tags = json.load(f)
                self.update_tag_display()
            except Exception as e:
                messagebox.showerror("Error Loading", str(e))
