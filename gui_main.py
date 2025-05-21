import customtkinter as ctk
from tkinter import messagebox, StringVar
from tag_configurator_tab import TagConfiguratorTab
from diagnostics_tab import DiagnosticsTab
from ChartTab import ChartTab
import subprocess
import os
import json
import threading
from datetime import datetime
from utils import initialize_db, DB_PATH

CONFIG_FILE = "plc_logger_config.json"

class TagEditorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PLC Logger Configurator")
        self.geometry("1000x850")
        self.tags = []
        self.global_settings = {
            "mode": "TCP",
            "ip": "192.168.0.10",
            "port": 502,
            "polling_interval": 0.5
        }
        self.db_file = None
        self.table_name = "plc_data"

        self.logging_thread = None
        self.logging_stop_event = threading.Event()

        self.create_widgets()
        self.load_config()
        self.bind_tab_change()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        # Settings panel
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.pack(padx=10, pady=(10, 0), fill="x")

        self.mode_option = ctk.CTkOptionMenu(self.settings_frame, values=["TCP", "ADS"])
        self.mode_option.set(self.global_settings["mode"])
        self.mode_option.grid(row=0, column=0, padx=10, pady=10)

        self.ip_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="IP Address")
        self.ip_entry.insert(0, self.global_settings["ip"])
        self.ip_entry.grid(row=0, column=1, padx=10, pady=10)

        self.port_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="Port")
        self.port_entry.insert(0, str(self.global_settings["port"]))
        self.port_entry.grid(row=0, column=2, padx=10, pady=10)

        self.polling_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="Polling Interval")
        self.polling_entry.insert(0, str(self.global_settings["polling_interval"]))
        self.polling_entry.grid(row=0, column=3, padx=10, pady=10)

        self.apply_button = ctk.CTkButton(self.settings_frame, text="Apply Settings", command=self.apply_settings)
        self.apply_button.grid(row=0, column=4, padx=10, pady=10)

        self.start_logging_button = ctk.CTkButton(self.settings_frame, text="Start Logging", command=self.start_logging)
        self.start_logging_button.grid(row=0, column=5, padx=10, pady=10)

        self.stop_logging_button = ctk.CTkButton(self.settings_frame, text="Stop Logging", command=self.stop_logging)
        self.stop_logging_button.grid(row=0, column=6, padx=10, pady=10)

        self.log_console = ctk.CTkTextbox(self, height=150)
        self.log_console.pack(fill="x", padx=10, pady=(5, 10))

        # Tag Filter Dropdown for Charts
        self.tag_filter_var = StringVar(value="All")
        self.tag_filter_dropdown = ctk.CTkOptionMenu(
            self,
            variable=self.tag_filter_var,
            values=["All"],
            command=lambda x: None
        )
        self.tag_filter_dropdown.pack(padx=10, pady=(0, 10), fill="x")

        # Tabs
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True)

        self.tabs.add("Diagnostics")
        self.tabs.add("Charts")
        self.tabs.add("Tag Configurator")

        self.diagnostics_tab = DiagnosticsTab(self.tabs.tab("Diagnostics"), self)
        self.diagnostics_tab.pack(fill="both", expand=True)

        self.chart_tab = ChartTab(self.tabs.tab("Charts"), self)
        self.chart_tab.pack(fill="both", expand=True)

        self.tag_configurator_tab = TagConfiguratorTab(self.tabs.tab("Tag Configurator"), self)
        self.tag_configurator_tab.grid(row=0, column=0, sticky="nsew")

    def update_tag_filter_dropdown(self):
        tag_names = ["All"]
        for tag in self.tags:
            if tag.get("enabled", True):
                tag_names.append(tag["name"].replace(" ", "_"))
        self.tag_filter_dropdown.configure(values=tag_names)
        self.tag_filter_var.set("All")

    def log_message(self, text):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_console.insert("end", f"{timestamp} - {text}\n")
        self.log_console.see("end")

    def apply_settings(self):
        try:
            self.global_settings["mode"] = self.mode_option.get()
            self.global_settings["ip"] = self.ip_entry.get()
            self.global_settings["port"] = int(self.port_entry.get())
            self.global_settings["polling_interval"] = float(self.polling_entry.get())
            messagebox.showinfo("Settings Updated", "Connection settings updated.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Port must be an integer. Polling interval must be a number.")

    def start_logging(self):
        self.apply_settings()
        initialize_db()
        self.db_file = DB_PATH

        mode = self.global_settings["mode"]

        def run_tcp():
            from tcp_logger import start_tcp_logging
            self.log_message("Starting Modbus TCP logging...")
            start_tcp_logging(stop_event=self.logging_stop_event, logger=self.log_message)

        def run_ads():
            from ads_data_pull import start_ads_data_pull
            self.log_message("Starting ADS logging...")
            start_ads_data_pull(stop_event=self.logging_stop_event, logger=self.log_message)

        self.logging_stop_event.clear()

        if mode == "TCP":
            self.logging_thread = threading.Thread(target=run_tcp, daemon=True)
            self.logging_thread.start()
            self.log_message("Modbus TCP logging started.")
        elif mode == "ADS":
            self.logging_thread = threading.Thread(target=run_ads, daemon=True)
            self.logging_thread.start()
            self.log_message("ADS logging started.")
        else:
            messagebox.showerror("Invalid Mode", f"Unsupported logging mode: {mode}")
            self.log_message(f"Unsupported mode: {mode}")

    def stop_logging(self):
        if self.logging_thread and self.logging_thread.is_alive():
            self.logging_stop_event.set()
            self.log_message("Logging stop requested.")
        else:
            self.log_message("No logging thread active.")

    def bind_tab_change(self):
        self.tabs._segmented_button._command = self.on_tab_changed

    def on_tab_changed(self, tab_name):
        if hasattr(self, "tag_configurator_tab") and self.tag_configurator_tab.unsaved_changes:
            if not messagebox.askyesno("Unsaved Changes", "You have unsaved tag changes. Switch tabs without saving?"):
                self.tabs.set("Tag Configurator")
                return
        self.tabs.set(tab_name)

    def save_config(self):
        config = {
            "global_settings": self.global_settings,
            "tags": self.tags
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
            self.update_tag_filter_dropdown()
        except Exception as e:
            print(f"Failed to save config: {e}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    self.global_settings.update(config.get("global_settings", {}))
                    self.tags = config.get("tags", [])
                self.update_tag_filter_dropdown()
            except Exception as e:
                print(f"Failed to load config: {e}")

    def on_close(self):
        if hasattr(self, "tag_configurator_tab") and self.tag_configurator_tab.unsaved_changes:
            if messagebox.askyesno("Unsaved Changes", "You have unsaved tag changes. Save before exiting?"):
                self.tag_configurator_tab.save_tags()
        self.save_config()
        self.destroy()

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = TagEditorApp()
    app.mainloop()
