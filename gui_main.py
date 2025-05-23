import customtkinter as ctk
from tkinter import messagebox, StringVar
from tag_configurator_tab import TagConfiguratorTab
from diagnostics_tab import DiagnosticsTab
from ChartTab import ChartTab
import os
import json
import threading
from datetime import datetime
from utils import initialize_db, DB_PATH
from tkinter import messagebox
import ipaddress
import re

def is_valid_ip(ip):
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
        
def is_valid_polling_interval(interval):
        try:
            value = float(interval)
            return 0.1 <= value <= 60.0
        except ValueError:
            return False
    
def is_valid_polling_interval(interval):
        try:
            value = float(interval)
            return 0.1 <= value <= 60.0
        except ValueError:
            return False    

def is_valid_ams_net_id(ams_id):
        return bool(re.match(r"^\d+\.\d+\.\d+\.\d+\.\d+\.\d+$", ams_id))    


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

        self._logging_active = False
        self._logging_flash_on = False
        self.logging_status_label = None  # Will be set in create_widgets


        self.create_widgets()
        self.load_config()
        self.bind_tab_change()
        self.protocol("WM_DELETE_WINDOW", self.on_close)




    def show_about_dialog(self):
        about_text = (
            "PLC Logger Configurator\n"
            "Version: 2.1\n"
            "Developer: Saeid Khosravani (saeid.k@sorsys.ca)\n\n"
            "Usage Tips:\n"
            "- Set your PLC connection at the top.\n"
            "- Wait for 'Read Success Rate = 100%' for auto logging start.\n"
            "- Use Start/Stop Logging buttons as needed.\n"
            "- Check Diagnostics and Charts for status and data.\n"
            "- All logs are saved to your Documents/PLC_Logs folder.\n"
        )
        from tkinter import messagebox
        messagebox.showinfo("About / Help", about_text)
     
    def _update_logging_status(self):
        """Flashes the green indicator when logging is active."""
        if self._logging_active:
            # Toggle the flash state
            self._logging_flash_on = not self._logging_flash_on
            color = "green" if self._logging_flash_on else "gray"
            self.logging_status_label.configure(text="● Logging", text_color=color)
            # Repeat after 500ms (for a 1 second cycle)
            self.after(500, self._update_logging_status)
        else:
            # Not logging, show solid gray
            self.logging_status_label.configure(text="● Not Logging", text_color="gray")
            self._logging_flash_on = False

   
    def handle_auto_start_logging(self):
        # Only start if not already running
        if not (self.logging_thread and self.logging_thread.is_alive()):
            self.log_message("PLC connection healthy. Auto-starting logging!")
            self.start_logging()

    
    def create_widgets(self):
        # Settings panel
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.pack(padx=10, pady=(10, 0), fill="x")

        # Row 0: Mode selection and entries
        self.mode_option = ctk.CTkOptionMenu(self.settings_frame, values=["TCP", "ADS"])
        self.mode_option.set(self.global_settings["mode"])
        self.mode_option.grid(row=0, column=0, padx=10, pady=10)

        self.ip_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="IP Address")
        self.ip_entry.insert(0, self.global_settings["ip"])
        self.ip_entry.grid(row=0, column=1, padx=10, pady=10)
        self.ip_note = ctk.CTkLabel(self.settings_frame, text="PLC IP address (e.g., 192.168.0.10)", text_color="gray", font=("Arial", 9, "italic"))
        self.ip_note.grid(row=1, column=1, padx=10, pady=(0, 5))

        self.port_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="Port")
        self.port_entry.insert(0, str(self.global_settings["port"]))
        self.port_entry.grid(row=0, column=2, padx=10, pady=10)
        self.port_note = ctk.CTkLabel(self.settings_frame, text="Default Modbus port is 502", text_color="gray", font=("Arial", 9, "italic"))
        self.port_note.grid(row=1, column=2, padx=10, pady=(0, 5))

        self.polling_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="Polling Interval")
        self.polling_entry.insert(0, str(self.global_settings["polling_interval"]))
        self.polling_entry.grid(row=0, column=3, padx=10, pady=10)
        self.polling_note = ctk.CTkLabel(self.settings_frame, text="Polling interval in seconds (e.g., 0.5)", text_color="gray", font=("Arial", 9, "italic"))
        self.polling_note.grid(row=1, column=3, padx=10, pady=(0, 5))

        # AMS Net ID Entry
        self.ams_id_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="AMS Net ID")
        self.ams_id_entry.insert(0, self.global_settings.get("ams_net_id", ""))
        self.ams_id_entry.grid(row=0, column=4, padx=10, pady=10)
        self.ams_id_note = ctk.CTkLabel(self.settings_frame, text="e.g., 5.132.118.239.1.1", text_color="gray", font=("Arial", 9, "italic"))
        self.ams_id_note.grid(row=1, column=4, padx=10, pady=(0, 5))

        # AMS Port Entry
        self.ams_port_entry = ctk.CTkEntry(self.settings_frame, placeholder_text="AMS Port")
        self.ams_port_entry.insert(0, str(self.global_settings.get("ams_port", 851)))
        self.ams_port_entry.grid(row=0, column=5, padx=10, pady=10)
        self.ams_port_note = ctk.CTkLabel(self.settings_frame, text="ADS TCP port (default: 851)", text_color="gray", font=("Arial", 9, "italic"))
        self.ams_port_note.grid(row=1, column=5, padx=10, pady=(0, 5))

        self.logging_status_label = ctk.CTkLabel(
            self.settings_frame,
            text="● Not Logging",
            text_color="gray",
            font=("Arial", 12, "bold"))
        self.logging_status_label.grid(row=0, column=6, padx=15, pady=10, sticky="e")
        self._update_logging_status()  # Ensure the indicator is correct at startup

        self.about_button = ctk.CTkButton(
        self.settings_frame,
        text="About / Help",
        width=110,
        command=self.show_about_dialog)
        self.about_button.grid(row=0, column=7, padx=10, pady=10, sticky="e")


        # Row 2: Buttons (apply, start, stop) in a new frame
        self.button_frame = ctk.CTkFrame(self.settings_frame)
        self.button_frame.grid(row=2, column=0, columnspan=4, padx=0, pady=(5, 0), sticky="w")

        self.apply_button = ctk.CTkButton(self.button_frame, text="Apply Settings", command=self.apply_settings)
        self.apply_button.pack(side="left", padx=10, pady=10)

        self.start_logging_button = ctk.CTkButton(self.button_frame, text="Start Logging", command=self.start_logging)
        self.start_logging_button.pack(side="left", padx=10, pady=10)

        self.stop_logging_button = ctk.CTkButton(self.button_frame, text="Stop Logging", command=self.stop_logging)
        self.stop_logging_button.pack(side="left", padx=10, pady=10)

        # Log Console and Tag Filter Dropdown remain unchanged
        self.log_console = ctk.CTkTextbox(self, height=150)
        self.log_console.pack(fill="x", padx=10, pady=(5, 10))

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

        self.diagnostics_tab.on_read_success = self.handle_auto_start_logging  # Patch for auto-start


        self.chart_tab = ChartTab(self.tabs.tab("Charts"), self)
        self.chart_tab.pack(fill="both", expand=True)

        self.tag_configurator_tab = TagConfiguratorTab(self.tabs.tab("Tag Configurator"), self)
        self.tag_configurator_tab.grid(row=0, column=0, sticky="nsew")

        self.mode_option.configure(command=self.update_ams_fields)
        self.update_ams_fields()



    def update_ams_fields(self, mode=None):
        if mode is None:
            mode = self.mode_option.get()
        if mode == "ADS":
            self.ams_id_entry.grid()
            self.ams_id_note.grid()
            self.ams_port_entry.grid()
            self.ams_port_note.grid()
        else:
            self.ams_id_entry.grid_remove()
            self.ams_id_note.grid_remove()
            self.ams_port_entry.grid_remove()
            self.ams_port_note.grid_remove()


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

    def apply_settings(self, show_info=True):
        # Get values from entries
        ams_net_id = self.ams_id_entry.get().strip()
        ams_port = self.ams_port_entry.get().strip()
        mode = self.mode_option.get()
        ip = self.ip_entry.get().strip()
        port = self.port_entry.get().strip()
        polling = self.polling_entry.get().strip()

        # IP Address validation
        if not is_valid_ip(ip):
            messagebox.showerror("Invalid Input", "Please enter a valid IP address.")
            return

        # Port validation
        try:
            port_val = int(port)
            if not (1 <= port_val <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Port must be an integer between 1 and 65535.")
            return

        # Polling interval validation
        if not is_valid_polling_interval(polling):
            messagebox.showerror("Invalid Input", "Polling interval must be a number between 0.1 and 60 seconds.")
            return

        # AMS Net ID and port validation (if in ADS mode)
        if mode == "ADS":
            if not is_valid_ams_net_id(ams_net_id):
                messagebox.showerror("Invalid Input", "AMS Net ID must be in the form X.X.X.X.X.X (six numbers separated by dots).")
                return
            try:
                ams_port_val = int(ams_port)
                if not (1 <= ams_port_val <= 65535):
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid Input", "AMS Port must be an integer between 1 and 65535.")
                return
            self.global_settings["ams_net_id"] = ams_net_id
            self.global_settings["ams_port"] = ams_port_val

        self.global_settings["mode"] = mode
        self.global_settings["ip"] = ip
        self.global_settings["port"] = port_val
        self.global_settings["polling_interval"] = float(polling)
        if show_info:
            messagebox.showinfo("Settings Updated", "Connection settings updated.")


    def start_logging(self):
        self.apply_settings(show_info=False)
        initialize_db()
        self.db_file = DB_PATH

        mode = self.global_settings["mode"]

        def run_tcp():
            from tcp_logger import start_tcp_logging
            self.log_message("Starting Modbus TCP logging...")

            # Use DiagnosticsTab.log_debug_message if it exists, fallback to self.log_message
            logger = getattr(self.diagnostics_tab, "log_debug_message", self.log_message)
            start_tcp_logging(stop_event=self.logging_stop_event, logger=logger)



        def run_ads():
            from ads_data_pull import start_ads_data_pull
            self.log_message("Starting ADS logging...")
            start_ads_data_pull(stop_event=self.logging_stop_event, logger=self.log_message)

        self.logging_stop_event.clear()

        if mode == "TCP":
            self.logging_thread = threading.Thread(target=run_tcp, daemon=True)
            self.logging_thread.start()
            self.log_message("Modbus TCP logging started.")
            self._logging_active = True
            self._update_logging_status()

        elif mode == "ADS":
            self.logging_thread = threading.Thread(target=run_ads, daemon=True)
            self.logging_thread.start()
            self.log_message("ADS logging started.")
            self._logging_active = True
            self._update_logging_status()

        else:
            messagebox.showerror("Invalid Mode", f"Unsupported logging mode: {mode}")
            self.log_message(f"Unsupported mode: {mode}")

    def stop_logging(self):
        if self.logging_thread and self.logging_thread.is_alive():
            self.logging_stop_event.set()
            self.log_message("Logging stop requested.")
            self._logging_active = False
            self._update_logging_status()
        else:
            self._logging_active = False
            self._update_logging_status()
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
            messagebox.showerror("Save Config Error", f"Failed to save config:\n{e}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    self.global_settings.update(config.get("global_settings", {}))
                    self.tags = config.get("tags", [])
                self.update_tag_filter_dropdown()
            except Exception as e:
                messagebox.showerror("Load Config Error", f"Failed to load config:\n{e}")

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
