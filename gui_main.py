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
import logging # Added
from main import APP_LOGGER_NAME # Added

# Get the central logger instance (APP_LOGGER_NAME is "" for root logger)
logger = logging.getLogger(__name__) # Use module's own logger, inherits root config

def is_valid_ip(ip: str) -> bool:
    """
    Validates if the given string is a valid IP address.

    Args:
        ip: The string to validate.

    Returns:
        True if valid IP, False otherwise.
    """
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
        
def is_valid_polling_interval(interval: str) -> bool:
    """
    Validates if the given string is a valid polling interval (0.1 to 60.0 seconds).

    Args:
        interval: The string to validate.

    Returns:
        True if valid, False otherwise.
    """
    try:
        value = float(interval)
        return 0.1 <= value <= 60.0
    except ValueError:
        return False   

def is_valid_ams_net_id(ams_id: str) -> bool:
    """
    Validates if the given string is a valid AMS Net ID (e.g., "1.2.3.4.5.6").

    Args:
        ams_id: The string to validate.

    Returns:
        True if valid, False otherwise.
    """
    return bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ams_id))


# --- Helper Functions for Input Validation ---

def validate_ip_address_input(ip_str):
    """Validates IP address and shows error message if invalid."""
    if not is_valid_ip(ip_str):
        messagebox.showerror("Invalid Input", "Please enter a valid IP address.")
        return False
    return True

def validate_port_input(port_str, port_name="Port"):
    """Validates port number and shows error message if invalid."""
    try:
        port_val = int(port_str)
        if not (1 <= port_val <= 65535):
            raise ValueError
        return port_val  # Return the validated integer value
    except ValueError:
        messagebox.showerror("Invalid Input", f"{port_name} must be an integer between 1 and 65535.")
        return None # Indicate failure

def validate_polling_interval_input(interval_str):
    """Validates polling interval and shows error message if invalid."""
    if not is_valid_polling_interval(interval_str):
        messagebox.showerror("Invalid Input", "Polling interval must be a number between 0.1 and 60 seconds.")
        return False
    return True

def validate_ams_net_id_input(ams_id_str):
    """Validates AMS Net ID and shows error message if invalid."""
    if not is_valid_ams_net_id(ams_id_str):
        messagebox.showerror("Invalid Input", "AMS Net ID must be in the form X.X.X.X.X.X (six numbers separated by dots).")
        return False
    return True

# --- End Helper Functions ---

CONFIG_FILE = "plc_logger_config.json" # TODO: Consider moving to utils.py if universally used


class TagEditorApp(ctk.CTk):
    """
    Main application class for the PLC Logger Configurator.

    This class sets up the main window, initializes UI components, manages global
    settings, handles PLC communication threads, and coordinates interactions
    between different tabs (Diagnostics, Charts, Tag Configurator).
    """
    def __init__(self):
        """Initializes the main application window and its components."""
        super().__init__()
        # self.logger = logging.getLogger(APP_LOGGER_NAME) # APP_LOGGER_NAME is ""
        self.logger = logging.getLogger(__name__) # Use module's own logger
        self.logger.info("Initializing TagEditorApp")

        self.title("PLC Logger Configurator")
        self.geometry("1000x850")
        self.tags = []
        self.global_settings = {
            "mode": "TCP",
            "ip": "192.168.0.10",
            "port": 502,
            "polling_interval": 0.5
            # ams_net_id and ams_port will be loaded or defaulted from config
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
        """Displays the 'About/Help' dialog with application information and usage tips."""
        self.logger.info("Showing About/Help dialog.")
        about_text = (
            "PLC Logger Configurator\n"
            "Version: 2.2\n" # Updated version
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
        """
        Handles the auto-start logging trigger from the DiagnosticsTab.

        Starts logging if the PLC connection is healthy and no logging thread is
        currently active.
        """
        if not (self.logging_thread and self.logging_thread.is_alive()):
            self.log_message("PLC connection healthy. Auto-starting logging!", level=logging.INFO)
            self.start_logging()
        else:
            self.logger.debug("Auto-start triggered, but logging thread is already active.")

    
    def create_widgets(self):
        """Creates and arranges all UI widgets in the main application window."""
        self.logger.debug("Creating widgets")
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

        self.diagnostics_tab = DiagnosticsTab(self.tabs.tab("Diagnostics"), self, logger_instance=self.logger) # Pass logger
        self.diagnostics_tab.pack(fill="both", expand=True)

        self.diagnostics_tab.on_read_success = self.handle_auto_start_logging  # Patch for auto-start


        self.chart_tab = ChartTab(self.tabs.tab("Charts"), self, logger_instance=self.logger) # Pass logger
        self.chart_tab.pack(fill="both", expand=True)

        self.tag_configurator_tab = TagConfiguratorTab(self.tabs.tab("Tag Configurator"), self, logger_instance=self.logger) # Pass logger
        self.tag_configurator_tab.grid(row=0, column=0, sticky="nsew")

        self.mode_option.configure(command=self.update_ams_fields)
        self.update_ams_fields()



    def update_ams_fields(self, mode: str = None):
        """
        Shows or hides AMS Net ID and AMS Port entry fields based on the selected mode.

        Args:
            mode: The communication mode ("TCP" or "ADS"). If None, it's read
                  from the mode_option widget.
        """
        if mode is None:
            mode = self.mode_option.get()
        
        self.logger.debug(f"Updating AMS fields visibility for mode: {mode}")
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
        """
        Updates the tag filter dropdown in the main GUI based on the current list
        of enabled tags. This dropdown is used by the ChartTab.
        """
        tag_names = ["All"]
        if self.tags: # Ensure self.tags is not None
            for tag in self.tags:
                if tag.get("enabled", True):
                    # Replace spaces with underscores for consistency if tag names are used as keys/identifiers
                    tag_names.append(tag["name"].replace(" ", "_"))
        self.tag_filter_dropdown.configure(values=tag_names)
        self.tag_filter_var.set("All") # Default to "All"
        self.logger.debug(f"Tag filter dropdown updated with tags: {tag_names}")

    def log_message(self, text: str, level: int = logging.INFO):
        """
        Logs a message to the GUI's log console and the central application logger.

        This method is thread-safe for GUI updates.

        Args:
            text: The message string to log.
            level: The logging level (e.g., logging.INFO, logging.ERROR).
        """
        timestamp = datetime.now().strftime('%H:%M:%S')
        gui_log_text = f"{timestamp} - {text}\n"
        
        # Safely update GUI console from any thread
        if self.log_console and self.log_console.winfo_exists(): # Check if widget exists
            self.after(0, self._update_log_console, gui_log_text)
        
        # Log to central logger
        self.logger.log(level, text)

    def _update_log_console(self, text: str):
        """Helper method to update the CTkTextbox log console from the main thread."""
        if self.log_console and self.log_console.winfo_exists():
            self.log_console.insert("end", text)
            self.log_console.see("end")
        else:
            # This case might occur if logging is called during shutdown
            self.logger.log(logging.WARNING, f"Attempted to log to GUI console, but widget no longer exists. Message: {text.strip()}")


    def _get_composite_logger(self):
        """
        Returns a logging function that directs messages to `self.log_message`.

        This ensures messages from background threads (tcp_logger, ads_data_pull)
        are logged to both the GUI console and the central application logger,
        and GUI updates are handled in a thread-safe manner.

        Returns:
            A function that can be called with a message string and optional log level.
        """
        def composite_log_func(message: str, level: int = logging.INFO):
            self.log_message(message, level)
        return composite_log_func


    def apply_settings(self, show_info: bool = True):
        """
        Validates and applies the global PLC connection settings from the UI.

        Updates `self.global_settings` dictionary. Optionally shows an info message
        on success.

        Args:
            show_info: If True, shows a success messagebox.
        """
        self.logger.info("Apply settings button clicked.")
        # Get values from entries
        ams_net_id = self.ams_id_entry.get().strip()
        ams_port = self.ams_port_entry.get().strip()
        mode = self.mode_option.get()
        ip = self.ip_entry.get().strip()
        port_str = self.port_entry.get().strip()
        polling_str = self.polling_entry.get().strip()

        if not validate_ip_address_input(ip):
            return

        port_val = validate_port_input(port_str)
        if port_val is None:
            return
        
        if not validate_polling_interval_input(polling_str):
            return

        if mode == "ADS":
            if not validate_ams_net_id_input(ams_net_id):
                return
            
            ams_port_val = validate_port_input(ams_port, port_name="AMS Port")
            if ams_port_val is None:
                return
            self.global_settings["ams_net_id"] = ams_net_id
            self.global_settings["ams_port"] = ams_port_val

        self.global_settings["mode"] = mode
        self.global_settings["ip"] = ip
        self.global_settings["port"] = port_val
        self.global_settings["polling_interval"] = float(polling_str) # polling_str is already validated
        if show_info:
            messagebox.showinfo("Settings Updated", "Connection settings updated.")
        self.logger.info(f"Settings applied: Mode={self.global_settings['mode']}, IP={self.global_settings['ip']}, Port={self.global_settings['port']}, Interval={self.global_settings['polling_interval']}")
        if self.global_settings['mode'] == "ADS":
            self.logger.info(f"ADS Settings: AMS Net ID={self.global_settings.get('ams_net_id')}, AMS Port={self.global_settings.get('ams_port')}")


    def start_logging(self):
        """
        Starts the PLC data logging process based on the current global settings.

        It applies the current settings, initializes the database if needed,
        and starts a new background thread for either TCP or ADS logging.
        """
        self.logger.info("Start Logging button clicked or called.")
        self.apply_settings(show_info=False) # Apply settings first
        
        if self.logging_thread and self.logging_thread.is_alive():
            self.log_message("Logging is already active. Please stop it before starting a new session.", level=logging.WARNING)
            messagebox.showwarning("Logging Active", "Logging is already in progress. Please stop the current session first.")
            return

        try:
            initialize_db() 
            self.db_file = DB_PATH # DB_PATH is set by initialize_db
            if not self.db_file: # Should not happen if initialize_db is correct
                self.log_message("Database path (DB_PATH) not set after initialize_db. Cannot start logging.", level=logging.ERROR)
                messagebox.showerror("DB Error", "Database path not configured. Check logs.")
                return
            self.log_message(f"Logging to database: {self.db_file}", level=logging.INFO)
        except Exception as e:
            self.log_message(f"Error initializing database: {e}", level=logging.CRITICAL)
            messagebox.showerror("DB Error", f"Fatal error initializing database: {e}\nCheck logs for details.")
            return

        mode = self.global_settings["mode"]
        worker_logger = self._get_composite_logger() 

        # Clear previous stop event and set logging active flag
        self.logging_stop_event.clear()
        self._logging_active = True # Set active before thread starts, thread will confirm actual start
        self._update_logging_status() # Update UI immediately

        if mode == "TCP":
            from tcp_logger import start_tcp_logging # Import locally to avoid circular deps if logger is in tcp_logger
            self.logging_thread = threading.Thread(target=start_tcp_logging, 
                                                 args=(self.logging_stop_event, worker_logger), 
                                                 daemon=True)
            self.log_message("Modbus TCP logging thread initiated.", level=logging.INFO)
        elif mode == "ADS":
            from ads_data_pull import start_ads_data_pull # Import locally
            self.logging_thread = threading.Thread(target=start_ads_data_pull, 
                                                 args=(self.logging_stop_event, worker_logger), 
                                                 daemon=True)
            self.log_message("ADS logging thread initiated.", level=logging.INFO)
        else:
            err_msg = f"Unsupported logging mode selected: {mode}"
            self.log_message(err_msg, level=logging.ERROR)
            messagebox.showerror("Invalid Mode", err_msg)
            self._logging_active = False # Reset flag as no thread started
            self._update_logging_status()
            return

        self.logging_thread.start()
        self.logger.info(f"{mode} logging thread started.")


    def stop_logging(self):
        """
        Stops the active PLC data logging thread.

        Sets an event to signal the logging thread to terminate and updates the UI.
        """
        self.logger.info("Stop Logging button clicked.")
        if self.logging_thread and self.logging_thread.is_alive():
            self.logging_stop_event.set() # Signal the thread to stop
            self.log_message("Logging stop requested. Waiting for thread to terminate...", level=logging.INFO)
            # Note: Actual thread termination and "stopped" message should come from the thread itself.
            # We might add a timeout join here if we want to wait for the thread, but
            # for UI responsiveness, it's often better to let it terminate gracefully.
        else:
            self.log_message("No active logging thread to stop.", level=logging.WARNING)
        
        self._logging_active = False # UI reflects stop request immediately
        self._update_logging_status()


    def bind_tab_change(self):
        """Binds the tab change event to a custom handler for unsaved changes checks."""
        self.logger.debug("Binding tab change event.")
        original_cmd = self.tabs._segmented_button._command
        
        def new_tab_command(selected_tab_name):
            self.logger.info(f"Tab changed to: {selected_tab_name}")
            if hasattr(self, "tag_configurator_tab") and self.tag_configurator_tab.unsaved_changes:
                self.logger.warning("Unsaved changes detected in Tag Configurator while switching tabs.")
                if not messagebox.askyesno("Unsaved Changes", "You have unsaved tag changes. Switch tabs without saving?"):
                    self.logger.info("User chose not to switch tabs due to unsaved changes.")
                    self.tabs.set("Tag Configurator") # Keep current tab
                    return 
            
            # If there's an original command associated with tab switching, call it.
            # For CTkTabview, setting the tab directly is usually the command.
            if original_cmd and original_cmd != self.on_tab_changed : # Avoid recursion if it was already this
                 original_cmd(selected_tab_name)
            else:
                 self.tabs.set(selected_tab_name) # Default action

        self.tabs._segmented_button.configure(command=new_tab_command)


    def on_tab_changed(self, tab_name): # This method might be redundant if logic is in new_tab_command
        # This method was previously assigned to self.tabs._segmented_button._command
        # The logic is now moved to the wrapper in bind_tab_change for clarity
        # Keeping it here for now in case it's called from somewhere else, though unlikely.
        self.logger.debug(f"on_tab_changed called with: {tab_name}")
        # The actual tab switching is handled by `self.tabs.set(tab_name)`
        # or the new_tab_command wrapper.
        pass


    def save_config(self):
        """
        Saves the current global settings and tags list to the configuration file.

        The configuration is saved in JSON format to `plc_logger_config.json`.
        """
        self.logger.info(f"Saving configuration to {CONFIG_FILE}")
        config = {
            "global_settings": self.global_settings,
            "tags": self.tags # Assumes self.tags is the source of truth from TagConfiguratorTab
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
            # self.update_tag_filter_dropdown() # Already called by TagConfiguratorTab.save_tags if changes there
            self.logger.info("Configuration saved successfully.")
        except Exception as e:
            self.logger.error(f"Failed to save application config: {e}", exc_info=True)
            messagebox.showerror("Save Config Error", f"Failed to save application configuration:\n{e}")

    def load_config(self):
        """
        Loads global settings and tags from the configuration file.

        If the file doesn't exist or is invalid, default settings are used.
        Updates UI elements to reflect the loaded configuration.
        """
        self.logger.info(f"Attempting to load configuration from {CONFIG_FILE}")
        # Default settings are already set in __init__
        # utils.load_config() handles file not found and JSON errors, returning defaults.
        
        loaded_config_data = {}
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded_config_data = json.load(f)
            self.logger.info(f"Successfully read {CONFIG_FILE}.")
        except FileNotFoundError:
            self.logger.warning(f"{CONFIG_FILE} not found. Using default settings and creating the file on next save.")
            # No need to do anything here, defaults from __init__ will be used.
            # File will be created on first save_config() call.
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding {CONFIG_FILE}: {e}. Using default settings.", exc_info=True)
            messagebox.showerror("Load Config Error", f"Error decoding configuration file:\n{e}\n\nDefault settings will be used.")
        except Exception as e: # Other potential errors like permission issues
            self.logger.error(f"Unexpected error loading {CONFIG_FILE}: {e}. Using default settings.", exc_info=True)
            messagebox.showerror("Load Config Error", f"Failed to load configuration: {e}\n\nDefault settings will be used.")

        # Apply loaded settings or ensure defaults are reflected
        loaded_global = loaded_config_data.get("global_settings", self.global_settings) # Use current if not in file
        # Ensure all expected keys are present, falling back to initial defaults
        for key, default_val in self.global_settings.items():
            self.global_settings[key] = loaded_global.get(key, default_val)
        
        self.tags = loaded_config_data.get("tags", []) # If "tags" key is missing, use empty list
        
        self.logger.info(f"Configuration applied: {len(self.tags)} tags, mode '{self.global_settings['mode']}'")

        # Update UI elements to reflect the loaded (or default) configuration
        self._update_ui_from_settings()
        
        if hasattr(self, 'tag_configurator_tab'): # Ensure tab is initialized
            self.tag_configurator_tab.tags = self.tags.copy() # Pass loaded tags to configurator
            self.tag_configurator_tab.load_tags() # Tell tab to refresh its display from its new self.tags


    def _update_ui_from_settings(self):
        """Helper to update UI elements from self.global_settings."""
        self.logger.debug("Updating UI elements from current global settings.")
        self.mode_option.set(self.global_settings["mode"])
        self.ip_entry.delete(0, 'end'); self.ip_entry.insert(0, self.global_settings["ip"])
        self.port_entry.delete(0, 'end'); self.port_entry.insert(0, str(self.global_settings["port"]))
        self.polling_entry.delete(0, 'end'); self.polling_entry.insert(0, str(self.global_settings["polling_interval"]))
        self.ams_id_entry.delete(0, 'end'); self.ams_id_entry.insert(0, self.global_settings.get("ams_net_id",""))
        self.ams_port_entry.delete(0, 'end'); self.ams_port_entry.insert(0, str(self.global_settings.get("ams_port",851)))
        self.update_ams_fields() 
        self.update_tag_filter_dropdown()


    def on_close(self):
        """Handles the application window close event."""
        self.logger.info("Application close requested.")
        if hasattr(self, "tag_configurator_tab") and self.tag_configurator_tab.unsaved_changes:
            self.logger.warning("Unsaved changes in Tag Configurator before closing.")
            if messagebox.askyesno("Unsaved Changes", "You have unsaved tag changes. Save before exiting?"):
                self.logger.info("User chose to save changes before exiting.")
                self.tag_configurator_tab.save_tags() # This calls self.app.save_config indirectly if needed
            else:
                self.logger.info("User chose NOT to save changes before exiting.")
        
        # Ensure logging is stopped gracefully
        if self.logging_thread and self.logging_thread.is_alive():
            self.logger.info("Stopping active logging thread before exit...")
            self.logging_stop_event.set()
            self.logging_thread.join(timeout=2.0) # Wait for thread to finish
            if self.logging_thread.is_alive():
                self.logger.warning("Logging thread did not terminate in time.")
        
        self.save_config() # Save current application settings (global, not tags if user skipped)
        self.logger.info("Destroying main application window.")
        self.destroy()

if __name__ == "__main__":
    # This block is for running gui_main.py directly.
    # In this case, we need to set up a basic logger if main.py's setup isn't run.
    # APP_LOGGER_NAME is "" for root logger.
    # Check if root logger has handlers.
    if not logging.getLogger().hasHandlers(): 
        # Basic setup for standalone run
        standalone_logger = logging.getLogger() # Get root logger
        standalone_logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # Use the same formatter as in main.py for consistency
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')
        ch.setFormatter(formatter)
        standalone_logger.addHandler(ch)
        standalone_logger.info("gui_main.py running in standalone mode: Basic root logger configured.")
    else:
        logging.getLogger(__name__).info("gui_main.py running, presumably launched from main.py with existing root logger config.")


    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = TagEditorApp()
    app.mainloop()
    logging.getLogger(__name__).info("gui_main.py standalone mainloop finished.")
