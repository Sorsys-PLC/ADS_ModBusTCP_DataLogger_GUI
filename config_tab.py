import customtkinter as ctk
import json
import os
from tkinter import messagebox

class ConfigurationTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.tags = []
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

        self.add_button = ctk.CTkButton(self, text="Add Tag", command=self.add_tag)
        self.add_button.grid(row=0, column=3, padx=10, pady=10)

        self.save_button = ctk.CTkButton(self, text="Save Tags", command=self.save_tags)
        self.save_button.grid(row=0, column=4, padx=10, pady=10)

        self.tag_display = ctk.CTkTextbox(self, width=800, height=200)
        self.tag_display.grid(row=1, column=0, columnspan=5, padx=10, pady=10)

    def add_tag(self):
        name = self.name_entry.get().strip()
        try:
            address = int(self.address_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Address", "Address must be an integer.")
            return
        tag_type = self.type_option.get()

        if not name:
            messagebox.showerror("Missing Name", "Please enter a tag name.")
            return

        # Check for duplicate address/type combo
        for tag in self.tags:
            if tag["address"] == address and tag["type"] == tag_type:
                messagebox.showerror("Duplicate Address", f"Another tag already uses address {address} as a {tag_type}.")
                return

        self.tags.append({"name": name, "address": address, "type": tag_type})
        self.update_tag_display()

    def update_tag_display(self):
        self.tag_display.delete("1.0", "end")
        seen = set()
        for tag in self.tags:
            label = f"{tag['name']} [{tag['type']} @ {tag['address']}]"
            key = (tag['type'], tag['address'])
            if key in seen:
                self.tag_display.insert("end", f"{label}  <-- DUPLICATE\n")
            else:
                self.tag_display.insert("end", f"{label}\n")
                seen.add(key)

    def save_tags(self):
        path = "plc_tag_config.json"
        try:
            with open(path, "w") as f:
                json.dump(self.tags, f, indent=4)
            messagebox.showinfo("Saved", f"Tags saved to {path}")
            self.app.tags = self.tags.copy()
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
