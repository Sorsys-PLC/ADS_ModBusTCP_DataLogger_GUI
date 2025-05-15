# tag_configurator_tab.py
import customtkinter as ctk
from tkinter import messagebox
import json

class TagConfiguratorTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.tags = []
        self.init_ui()
        self.load_tags()

    def init_ui(self):
        self.tag_listbox = ctk.CTkTextbox(self, width=400, height=200)
        self.tag_listbox.grid(row=0, column=0, columnspan=4, padx=10, pady=(10, 0))

        self.name_entry = ctk.CTkEntry(self, placeholder_text="Tag Name")
        self.name_entry.grid(row=1, column=0, padx=10, pady=10)

        self.addr_entry = ctk.CTkEntry(self, placeholder_text="Address")
        self.addr_entry.grid(row=1, column=1, padx=10, pady=10)

        self.type_option = ctk.CTkOptionMenu(self, values=["Coil", "Register"])
        self.type_option.set("Register")
        self.type_option.grid(row=1, column=2, padx=10, pady=10)

        self.add_button = ctk.CTkButton(self, text="Add Tag", command=self.add_tag)
        self.add_button.grid(row=1, column=3, padx=10, pady=10)

        self.save_button = ctk.CTkButton(self, text="Save Tags", command=self.save_tags)
        self.save_button.grid(row=2, column=3, padx=10, pady=10)

    def add_tag(self):
        name = self.name_entry.get().strip()
        addr = self.addr_entry.get().strip()
        ttype = self.type_option.get().strip()

        if not name or not addr:
            messagebox.showwarning("Input Error", "Tag name and address are required.")
            return

        tag = {"name": name, "address": addr, "type": ttype}
        self.tags.append(tag)
        self.update_listbox()

        self.name_entry.delete(0, 'end')
        self.addr_entry.delete(0, 'end')

    def update_listbox(self):
        self.tag_listbox.delete("1.0", "end")
        for tag in self.tags:
            self.tag_listbox.insert("end", f"{tag['name']} [{tag['type']} @ {tag['address']}]\n")

    def save_tags(self):
        with open("plc_tag_config.json", "w") as f:
            json.dump(self.tags, f, indent=2)
        messagebox.showinfo("Saved", "Tag configuration saved.")
        self.app.tags = self.tags
        self.app.update_tag_filter_dropdown()

    def load_tags(self):
        try:
            with open("plc_tag_config.json", "r") as f:
                self.tags = json.load(f)
                self.update_listbox()
                self.app.tags = self.tags
                self.app.update_tag_filter_dropdown()
        except FileNotFoundError:
            pass

# Integration snippet (to include in LoggerGUI.py):
# from tag_configurator_tab import TagConfiguratorTab
# ... inside create_widgets():
# self.tag_configurator_frame = TagConfiguratorTab(self.tabs, self)
# self.tabs.add(self.tag_configurator_frame, text="Tag Configurator")
