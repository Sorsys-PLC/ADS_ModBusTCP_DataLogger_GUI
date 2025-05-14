import customtkinter as ctk
import json
import os
from tkinter import messagebox
from datetime import datetime
import hashlib

CONFIG_FILE = "plc_logger_config.json"

class TagEditorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PLC Logger Configurator")
        self.geometry("700x600")
        self.tags = []
        self.config_hash = None
        self.version = 1
        self.global_settings = {
            "mode": "TCP",
            "ip": "192.168.0.10",
            "port": 502,
            "polling_interval": 0.5
        }

        self.create_widgets()
        self.load_config()

    def create_widgets(self):
        # Global settings
        self.mode_option = ctk.CTkOptionMenu(self, values=["TCP", "ADS"])
        self.mode_option.set(self.global_settings["mode"])
        self.mode_option.grid(row=0, column=0, padx=10, pady=10)

        self.ip_entry = ctk.CTkEntry(self, placeholder_text="IP Address")
        self.ip_entry.insert(0, self.global_settings["ip"])
        self.ip_entry.grid(row=0, column=1, padx=10, pady=10)

        self.port_entry = ctk.CTkEntry(self, placeholder_text="Port")
        self.port_entry.insert(0, str(self.global_settings["port"]))
        self.port_entry.grid(row=0, column=2, padx=10, pady=10)

        self.polling_entry = ctk.CTkEntry(self, placeholder_text="Polling Interval")
        self.polling_entry.insert(0, str(self.global_settings["polling_interval"]))
        self.polling_entry.grid(row=0, column=3, padx=10, pady=10)

        # Tag input fields
        self.name_entry = ctk.CTkEntry(self, placeholder_text="Tag Name")
        self.name_entry.grid(row=1, column=0, padx=10, pady=10)

        self.type_option = ctk.CTkOptionMenu(self, values=["coil", "register"])
        self.type_option.set("coil")
        self.type_option.grid(row=1, column=1, padx=10, pady=10)

        self.address_entry = ctk.CTkEntry(self, placeholder_text="Address")
        self.address_entry.grid(row=1, column=2, padx=10, pady=10)

        self.scale_entry = ctk.CTkEntry(self, placeholder_text="Scale (optional)")
        self.scale_entry.grid(row=1, column=3, padx=10, pady=10)

        self.add_button = ctk.CTkButton(self, text="Add Tag", command=self.add_tag)
        self.add_button.grid(row=1, column=4, padx=10, pady=10)

        # Tag list display
        self.tag_listbox = ctk.CTkTextbox(self, width=650, height=300)
        self.tag_listbox.grid(row=2, column=0, columnspan=5, padx=10, pady=10)

        # Save button
        self.save_button = ctk.CTkButton(self, text="Save Config", command=self.save_config)
        self.save_button.grid(row=3, column=0, columnspan=5, pady=10)

    def add_tag(self):
        name = self.name_entry.get()
        tag_type = self.type_option.get()
        address = self.address_entry.get()
        scale = self.scale_entry.get()

        if not name or not address.isdigit():
            messagebox.showerror("Input Error", "Please enter a valid name and numeric address.")
            return

        tag = {
            "name": name,
            "type": tag_type,
            "address": int(address),
            "scale": float(scale) if scale else 1.0,
            "enabled": True
        }
        self.tags.append(tag)
        self.update_tag_display()

        # Clear inputs
        self.name_entry.delete(0, 'end')
        self.address_entry.delete(0, 'end')
        self.scale_entry.delete(0, 'end')

    def update_tag_display(self):
        self.tag_listbox.delete("1.0", "end")
        for idx, tag in enumerate(self.tags, start=1):
            line = f"{idx}. {tag['name']} ({tag['type']} @ {tag['address']}, scale={tag['scale']})\n"
            self.tag_listbox.insert("end", line)

    def calculate_hash(self, tags):
        return hashlib.md5(json.dumps(tags, sort_keys=True).encode()).hexdigest()

    def save_config(self):
        self.global_settings = {
            "mode": self.mode_option.get(),
            "ip": self.ip_entry.get(),
            "port": int(self.port_entry.get()),
            "polling_interval": float(self.polling_entry.get())
        }

        config = {
            "tags": self.tags,
            "settings": self.global_settings
        }
        new_hash = self.calculate_hash(self.tags)

        if new_hash != self.config_hash:
            versioned_file = f"plc_logger_config_v{self.version}.json"
            while os.path.exists(versioned_file):
                self.version += 1
                versioned_file = f"plc_logger_config_v{self.version}.json"

            with open(versioned_file, "w") as f:
                json.dump(config, f, indent=4)

            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)

            self.config_hash = new_hash
            messagebox.showinfo("Saved", f"Configuration saved as {versioned_file}")
        else:
            messagebox.showinfo("No Change", "Configuration unchanged. No new file created.")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                self.tags = config.get("tags", [])
                self.global_settings = config.get("settings", self.global_settings)
                self.mode_option.set(self.global_settings["mode"])
                self.ip_entry.delete(0, 'end')
                self.ip_entry.insert(0, self.global_settings["ip"])
                self.port_entry.delete(0, 'end')
                self.port_entry.insert(0, str(self.global_settings["port"]))
                self.polling_entry.delete(0, 'end')
                self.polling_entry.insert(0, str(self.global_settings["polling_interval"]))
                self.config_hash = self.calculate_hash(self.tags)
                self.update_tag_display()

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = TagEditorApp()
    app.mainloop()