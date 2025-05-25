import customtkinter as ctk
from datetime import datetime
from tkinter import END
from pyModbusTCP.client import ModbusClient
import logging # Added
# Assuming APP_LOGGER_NAME is accessible if this module needs a fallback logger.
# from main import APP_LOGGER_NAME # Or pass APP_LOGGER_NAME for fallback

class DiagnosticsTab(ctk.CTkFrame):
    """
    A CustomTkinter frame providing a diagnostics interface for PLC communication.

    This tab displays real-time information about the connection status to the PLC,
    ping times, read success rates, and a log of recent error messages. It also
    allows users to manually test the connection. An automatic logging start
    can be triggered if a callback (`on_read_success`) is provided and the
    connection is consistently healthy.

    Attributes:
        app: Reference to the main `TagEditorApp` instance.
        logger: Logger instance for logging messages.
        ping_history (list[float]): Stores recent ping times in milliseconds.
        error_messages (list[str]): Stores recent error messages related to PLC communication.
        success_count (int): Count of successful diagnostic reads.
        fail_count (int): Count of failed diagnostic reads.
        on_read_success (callable | None): A callback function to be invoked when
                                           the read success rate reaches 100% after
                                           a certain number of attempts. Used for
                                           auto-starting the main logging process.
        _auto_start_triggered (bool): Flag to ensure `on_read_success` is triggered only once.
    """
    def __init__(self, master, app, logger_instance: logging.Logger = None, **kwargs):
        """
        Initializes the DiagnosticsTab.

        Args:
            master: The parent widget.
            app: The main application instance (`TagEditorApp`).
            logger_instance: An optional logger instance. If None, a new logger
                             specific to this tab will be created.
            **kwargs: Additional keyword arguments for `ctk.CTkFrame`.
        """
        super().__init__(master, **kwargs)
        self.app = app
        # Use the passed logger instance, or get one if not provided (for standalone use or testing)
        self.logger = logger_instance if logger_instance else logging.getLogger("PLCLoggerApp_DiagnosticsTab") # Fallback name
        if not logger_instance:
            self.logger.warning("No central logger provided to DiagnosticsTab; using fallback.")
            if not self.logger.hasHandlers(): # Basic config for fallback if no handlers exist
                ch = logging.StreamHandler()
                ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s'))
                self.logger.addHandler(ch)
                self.logger.setLevel(logging.DEBUG)


        self.ping_history = []
        self.error_messages = []
        self.success_count = 0
        self.fail_count = 0
        self.on_read_success = None  # ADD THIS: callback for read success
        self._auto_start_triggered = False  # ADD THIS: to ensure one-time trigge
        self.create_widgets()
        self.after(5000, self.update_diagnostics) # Start periodic diagnostic updates


    def log_debug_message(self, msg: str, level: int = logging.DEBUG):
        """
        Logs a message to this tab's error log text box and the central logger.

        This method is typically called by other parts of the application (like
        the main app or logging workers via a composite logger) to display
        status or error messages within the Diagnostics tab's UI.

        Args:
            msg: The message string to log.
            level: The logging level for the central logger.
        """
        self.logger.log(level, f"[DIAG_UI_LOG] {msg}") # Log to central logger with context

        # Update GUI's error_log text box
        # This method might be called from different threads (e.g., via composite logger
        # from worker threads). `self.after(0, ...)` could be used here for strict
        # thread safety, but CTk/Tkinter textbox appends are often tolerant if mostly
        # from main or via `self.app.log_message` which itself uses `after`.
        # For simplicity, direct update if this method is primarily called by `self.app.log_message`.
        try:
            gui_msg = msg if msg.endswith("\n") else msg + "\n"
            if self.error_log and self.error_log.winfo_exists():
                self.error_log.insert("end", gui_msg)
                self.error_log.see("end")
            else:
                self.logger.warning("DiagnosticsTab error_log widget not available for logging.")
        except Exception as e:
            self.logger.error(f"Failed to write to DiagnosticsTab's error_log: {e}", exc_info=True)


    def create_widgets(self):
        """Creates and arranges all UI widgets within the DiagnosticsTab."""
        self.logger.debug("Creating DiagnosticsTab widgets.")
        self.connection_status_label = ctk.CTkLabel(self, text="Connection: Unknown")
        self.connection_status_label.pack(pady=10)

        self.last_ping_label = ctk.CTkLabel(self, text="Last Ping: N/A")
        self.last_ping_label.pack(pady=5)

        self.success_rate_label = ctk.CTkLabel(self, text="Read Success Rate: N/A")
        self.success_rate_label.pack(pady=5)

        self.error_log = ctk.CTkTextbox(self, width=800, height=150)
        self.error_log.pack(pady=10)

        self.test_button = ctk.CTkButton(self, text="Test Connection", command=self.test_connection)
        self.test_button.pack(pady=10)

    def update_diagnostics(self):
        """
        Periodically pings the configured PLC to update connection status and statistics.
        
        This method attempts a simple Modbus read operation (read first coil)
        to check connectivity. It updates UI labels for connection status,
        last ping time, and read success rate. Recent error messages are displayed
        in the error log text box. If the read success rate is consistently high,
        it may trigger the `self.on_read_success` callback for auto-starting logging.
        This method schedules itself to run again via `self.after()`.
        """
        # Ensure global_settings are available from the app instance
        if not hasattr(self.app, 'global_settings'):
            self.logger.error("DiagnosticsTab: self.app.global_settings not found. Cannot perform diagnostics.")
            self.connection_status_label.configure(text="Connection: Error (App settings missing)")
            self.after(5000, self.update_diagnostics) # Retry later
            return

        ip = self.app.global_settings.get("ip", "127.0.0.1")
        port = self.app.global_settings.get("port", 502)
        
        # Only perform diagnostics if IP and port are set (especially important for ADS mode where they might be empty)
        if not ip or (self.app.global_settings.get("mode") == "TCP" and not port): # For TCP, port is essential
            self.logger.debug(f"Diagnostics skipped: IP or Port not set for mode {self.app.global_settings.get('mode')}.")
            self.connection_status_label.configure(text="Connection: Not Configured")
            self.last_ping_label.configure(text="Last Ping: N/A")
            self.success_rate_label.configure(text="Read Success Rate: N/A")
            self.after(5000, self.update_diagnostics) # Schedule next attempt
            return

        self.logger.debug(f"Updating diagnostics: Pinging {ip}:{port} (Mode: {self.app.global_settings.get('mode')})")
        
        # For ADS mode, ModbusClient ping is not applicable.
        # This diagnostic is Modbus specific. A more generic ping or ADS-specific check would be needed for ADS.
        # For now, we'll assume this diagnostic is primarily for Modbus TCP.
        if self.app.global_settings.get("mode") != "TCP":
            self.logger.debug(f"Diagnostics ping skipped for non-TCP mode ({self.app.global_settings.get('mode')}).")
            self.connection_status_label.configure(text=f"Connection: N/A for {self.app.global_settings.get('mode')} mode")
            self.last_ping_label.configure(text="Last Ping: N/A")
            self.success_rate_label.configure(text="Read Success Rate: N/A")
            self.after(5000, self.update_diagnostics)
            return

        client = ModbusClient(host=ip, port=port, auto_open=True, timeout=2)
        start_time = datetime.now()
        ping_error_msg = None
        success = False

        try:
            # Reading a single coil is a lightweight way to check Modbus TCP connectivity
            result = client.read_coils(0, 1) 
            if result is not None:
                success = True
            else:
                ping_error_msg = "Read failed (no data or None returned from read_coils)."
                self.logger.warning(f"Diagnostics ping to {ip}:{port} - read_coils returned None.")
        except Exception as e:
            ping_error_msg = str(e)
            self.logger.warning(f"Diagnostics ping to {ip}:{port} failed: {e}", exc_info=False) 

        if ping_error_msg and (not self.error_messages or ping_error_msg not in self.error_messages[-1]): 
             self.error_messages.append(f"{datetime.now().strftime('%H:%M:%S')} - {ping_error_msg}")

        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        self.ping_history.append(elapsed) 
        if len(self.ping_history) > 20: 
            self.ping_history.pop(0)

        if success:
            self.success_count += 1
            self.connection_status_label.configure(text="Connection: ✅ Connected")
        else:
            self.fail_count += 1
            self.connection_status_label.configure(text="Connection: ❌ Failed")

        self.last_ping_label.configure(text=f"Last Ping: {int(elapsed)} ms")
        total_reads = self.success_count + self.fail_count
        if total_reads > 0:
            rate = int((self.success_count / total_reads) * 100)
            self.success_rate_label.configure(text=f"Read Success Rate: {rate}% ({self.success_count}/{total_reads})")
            
            if rate == 100 and total_reads >= 3 and not self._auto_start_triggered : 
                self.logger.info(f"Read success rate 100% after {total_reads} attempts. Triggering auto-start callback.")
                self._auto_start_triggered = True 
                if callable(self.on_read_success):
                    self.on_read_success()
        else:
            self.success_rate_label.configure(text="Read Success Rate: N/A")

        if self.error_messages:
            unique_recent_errors = []
            for msg in reversed(self.error_messages[-10:]): # Look at last 10 for uniqueness
                if msg not in unique_recent_errors:
                    unique_recent_errors.insert(0, msg)
                if len(unique_recent_errors) >= 5: 
                    break
            
            if self.error_log and self.error_log.winfo_exists():
                self.error_log.delete("1.0", END)
                self.error_log.insert("end", "\n".join(unique_recent_errors))
                self.error_log.see("end")

        self.after(5000, self.update_diagnostics) 

    def test_connection(self):
        """
        Manually triggers a connection test by resetting diagnostic counters
        and scheduling an immediate update.
        """
        self.logger.info("Manual connection test initiated from DiagnosticsTab.")
        self.fail_count = 0
        self.success_count = 0
        self._auto_start_triggered = False 
        self.error_messages.clear()
        if self.error_log and self.error_log.winfo_exists():
            self.error_log.delete("1.0", END) 
        self.log_debug_message("Manual connection test running...", level=logging.INFO)
        self.update_diagnostics() 
