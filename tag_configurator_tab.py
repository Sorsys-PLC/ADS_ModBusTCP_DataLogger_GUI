import customtkinter as ctk
import json
import os
import re
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
        tooltip_font = ("Arial", 10, "italic")
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(padx=10, pady=10, fill="x")

        self.name_entry = ctk.CTkEntry(form_frame, placeholder_text="Tag Name")
        self.name_entry_tooltip = ctk.CTkLabel(form_frame, text="Enter a unique name for the tag", font=tooltip_font, text_color="gray")
        self.name_entry.grid(row=0, column=0, padx=5, pady=5)
        self.name_entry_tooltip.grid(row=1, column=0, padx=5, pady=(0, 10))

        self.address_entry = ctk.CTkEntry(form_frame, placeholder_text="Address")
        self.address_entry_tooltip = ctk.CTkLabel(form_frame, text="Integer address (e.g., 0, 1, 100)", font=tooltip_font, text_color="gray")
        self.address_entry.grid(row=0, column=1, padx=5, pady=5)
        self.address_entry_tooltip.grid(row=1, column=1, padx=5, pady=(0, 10))

        self.type_option = ctk.CTkOptionMenu(form_frame, values=["Coil", "Register"])
        self.type_option.set("Coil")
        self.type_option_tooltip = ctk.CTkLabel(form_frame, text="Choose tag type", font=tooltip_font, text_color="gray")
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

        self.remove_button = ctk.CTkButton(button_frame, text="Remove Tag", command=self.remove_tag)
        self.remove_button.pack(side="left", padx=5)

        self.save_button = ctk.CTkButton(button_frame, text="Save Tags", command=self.save_tags)
        self.save_button.pack(side="left", padx=5)

        self.tag_display = ctk.CTkTextbox(self, width=800, height=200)
        self.tag_display.pack(padx=10, pady=10, fill="both", expand=True)

    def clean_tag_name(self, name):
        # Remove all non-printable and normalize whitespace
        name = name.strip()
        name = re.sub(r'\s+', ' ', name)
        return name

    def update_tag_display(self):
        self.tag_display.delete("1.0", "end")
        seen = set()
        for tag in self.tags:
            # Show the repr to catch hidden spaces
            label = f"{repr(tag['name'])} [{tag['type']} @ {tag['address']}]"
            key = (tag['type'], tag['address'])
            enabled_status = "Enabled" if tag.get("enabled", True) else "Disabled"
            if key in seen:
                self.tag_display.insert("end", f"{label} ({enabled_status})  <-- DUPLICATE\n")
            else:
                self.tag_display.insert("end", f"{label} ({enabled_status})\n")
                seen.add(key)

    def add_tag(self):
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

        self.tags.append({"name": name, "address": address, "type": tag_type, "enabled": enabled})
        self.unsaved_changes = True
        self.save_button.configure(fg_color="#FFA500")
        self.update_tag_display()

    def save_tags(self):
        seen = {}
        duplicates = []
        name_set = set()
        # Debug printout of tag names for visibility

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
        path = "plc_logger_config.json"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    config = json.load(f)
                    self.tags = config.get("tags", [])
                self.update_tag_display()
            except Exception as e:
                messagebox.showerror("Error Loading", str(e))
