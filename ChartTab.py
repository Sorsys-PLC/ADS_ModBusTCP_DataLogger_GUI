import customtkinter as ctk
from tkinter import messagebox, filedialog
import sqlite3
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
import threading
import os
import logging # Added
# from main import APP_LOGGER_NAME # Or pass APP_LOGGER_NAME for fallback

PLC_LOGS_DIR = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Documents", "PLC_Logs")
"""Directory where PLC log database files are stored."""

class ChartTab(ctk.CTkFrame):
    """
    A CustomTkinter frame that provides UI for selecting and displaying PLC log data charts.

    This tab allows users to:
    - Select a database file from the `PLC_LOGS_DIR`.
    - Select a specific tag from the chosen database to plot.
    - Specify a date and time range for the chart.
    - Enable auto-refresh for the chart with a configurable interval.
    - View the chart rendered using Matplotlib.
    - Save the displayed chart to an image file.
    - Export the charted data to a CSV file.

    Attributes:
        app: Reference to the main `TagEditorApp` instance.
        logger: Logger instance for logging messages.
        db_file (str | None): Full path to the currently selected SQLite database file.
        tag_list (list[str]): List of available tag names from the selected database.
        figure (matplotlib.figure.Figure | None): The Matplotlib figure object for the current chart.
        canvas (FigureCanvasTkAgg | None): The Tkinter canvas embedding the Matplotlib chart.
        auto_refresh (bool): Flag indicating if auto-refresh is enabled.
        loading_label (ctk.CTkLabel | None): Label displayed while chart data is loading.
    """
    def __init__(self, master, app, logger_instance: logging.Logger = None, **kwargs):
        """
        Initializes the ChartTab.

        Args:
            master: The parent widget.
            app: The main application instance (`TagEditorApp`).
            logger_instance: An optional logger instance. If None, a new logger
                             specific to this tab will be created.
            **kwargs: Additional keyword arguments for `ctk.CTkFrame`.
        """
        super().__init__(master, **kwargs)
        self.app = app
        # Use the passed logger instance, or get one if not provided
        self.logger = logger_instance if logger_instance else logging.getLogger("PLCLoggerApp_ChartTab") # Fallback
        if not logger_instance:
            self.logger.warning("No central logger provided to ChartTab; using fallback.")
            if not self.logger.hasHandlers(): # Basic config for fallback
                ch = logging.StreamHandler()
                ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s'))
                self.logger.addHandler(ch)
                self.logger.setLevel(logging.DEBUG)
        
        self.logger.debug("Initializing ChartTab")
        self.auto_refresh = False
        self.canvas = None
        self.figure = None
        self.loading_label = None

        self.db_file = None
        self.table_name = "plc_data"
        self.tag_list = []

        self.init_ui()
        self.populate_db_dropdown()

    def init_ui(self):
        """Initializes and arranges all UI widgets within the ChartTab."""
        self.logger.debug("Initializing ChartTab UI elements.")
        self.db_var = ctk.StringVar(value="Select Database...") # Initialize with placeholder
        self.db_dropdown = ctk.CTkOptionMenu(self, variable=self.db_var, values=["Select Database..."], command=self.on_db_selected)
        self.db_dropdown.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.db_dropdown.configure(width=320)
        # self.db_dropdown.set("Select Database...") # Already set by StringVar

        self.tag_var = ctk.StringVar(value="All")
        self.tag_filter_dropdown = ctk.CTkOptionMenu(self, variable=self.tag_var, values=["All"])
        self.tag_filter_dropdown.grid(row=0, column=1, padx=5, pady=5)
        self.tag_filter_dropdown.set("All")

        self.start_date_entry = ctk.CTkEntry(self, placeholder_text="Start Date (YYYY-MM-DD)")
        self.start_date_entry.grid(row=1, column=0, padx=5, pady=5)
        self.end_date_entry = ctk.CTkEntry(self, placeholder_text="End Date (YYYY-MM-DD)")
        self.end_date_entry.grid(row=1, column=1, padx=5, pady=5)
        self.start_time_entry = ctk.CTkEntry(self, placeholder_text="Start Time (HH:MM:SS)")
        self.start_time_entry.grid(row=1, column=2, padx=5, pady=5)
        self.end_time_entry = ctk.CTkEntry(self, placeholder_text="End Time (HH:MM:SS)")
        self.end_time_entry.grid(row=1, column=3, padx=5, pady=5)
        self.refresh_interval_entry = ctk.CTkEntry(self, placeholder_text="Refresh Interval (s)")
        self.refresh_interval_entry.insert(0, "5")
        self.refresh_interval_entry.grid(row=1, column=4, padx=5, pady=5)
        self.auto_refresh_checkbox = ctk.CTkCheckBox(self, text="Auto Refresh", command=self.toggle_auto_refresh)
        self.auto_refresh_checkbox.grid(row=1, column=5, padx=5, pady=5)
        self.view_button = ctk.CTkButton(self, text="View Chart", command=self.show_chart)
        self.view_button.grid(row=2, column=0, columnspan=2, pady=10)
        self.save_button = ctk.CTkButton(self, text="Save Chart", command=self.save_chart)
        self.save_button.grid(row=2, column=2, padx=5, pady=10)
        self.export_button = ctk.CTkButton(self, text="Export CSV", command=self.export_chart_data)
        self.export_button.grid(row=2, column=3, padx=5, pady=10)
        self.chart_frame = ctk.CTkFrame(self)
        self.chart_frame.grid(row=3, column=0, columnspan=6, padx=10, pady=10, sticky="nsew")

    def populate_db_dropdown(self):
        """
        Populates the database selection dropdown with `.db` files from `PLC_LOGS_DIR`.

        Files are parsed to extract date, time, and configuration hash from their
        names (expected format: `plc_data_YYYY-MM-DD_HHMMSS_config-<hash>.db`).
        The list is sorted to show the newest databases first.
        If a valid database is auto-selected, `on_db_selected` is called.
        """
        import re # For parsing filenames
        self.logger.debug(f"Populating DB dropdown. PLC_LOGS_DIR: {PLC_LOGS_DIR}")
        if not os.path.exists(PLC_LOGS_DIR):
            try:
                os.makedirs(PLC_LOGS_DIR, exist_ok=True)
                self.logger.info(f"Created PLC_LOGS_DIR at {PLC_LOGS_DIR}")
            except OSError as e:
                self.logger.error(f"Failed to create PLC_LOGS_DIR at {PLC_LOGS_DIR}: {e}", exc_info=True)
                # Display error to user as this is critical for DB selection
                messagebox.showerror("Directory Error", f"Cannot create log directory: {PLC_LOGS_DIR}\nPlease check permissions.")
                self.db_dropdown.configure(values=["Error: Check Logs Dir"])
                self.db_var.set("Error: Check Logs Dir")
                return

        db_files_data = []
        # Regex to capture date, time, and config hash
        # plc_data_YYYY-MM-DD_HHMMSS_config-<hash>.db
        # Example: plc_data_2023-10-26_103000_config-a1b2c3d4.db
        # Or: plc_data_2023-10-26_103000.db (if no hash)
        file_pattern = re.compile(r"plc_data_(\d{4}-\d{2}-\d{2})_(\d{6})(?:_config-([a-fA-F0-9]+))?\.db")

        raw_files = os.listdir(PLC_LOGS_DIR)
        for f_name in raw_files:
            if f_name.lower().endswith(".db"):
                match = file_pattern.match(f_name)
                if match:
                    date_str, time_str, config_hash = match.groups()
                    config_hash = config_hash or "000000" # Default hash if not present, for sorting
                    db_files_data.append({
                        "filename": f_name,
                        "path": os.path.join(PLC_LOGS_DIR, f_name),
                        "date": date_str,
                        "time": time_str,
                        "hash": config_hash
                    })
                else:
                    # Fallback for files not matching the new pattern, treat them as older
                    # Or, if you want to strictly adhere, you can skip these or log an error.
                    # For now, let's try to get a date from the filename if possible, or use file mod time.
                    # This part can be complex if formats are very inconsistent.
                    # A simpler approach: if it doesn't match, it won't be preferred.
                    # For now, we only consider files matching the pattern.
                    self.logger.warning(f"Skipping file due to naming format mismatch: {f_name}")


        # Sort files: date (desc), time (desc), hash (desc)
        db_files_data.sort(key=lambda x: (x["date"], x["time"], x["hash"]), reverse=True)
        self.logger.debug(f"Found and sorted {len(db_files_data)} DB files.")

        display_filenames = [item["filename"] for item in db_files_data]
        
        current_selection = self.db_var.get()
        
        if not db_files_data:
            self.db_dropdown.configure(values=["Select Database..."])
            self.db_var.set("Select Database...")
            self.on_db_selected("Select Database...") # Ensure tags are cleared etc.
            return

        self.db_dropdown.configure(values=display_filenames)

        # Check if current selection is still valid, otherwise pick the latest
        if current_selection != "Select Database..." and current_selection in display_filenames:
            self.db_var.set(current_selection) # Keep current valid selection
            # No automatic call to on_db_selected here unless it's the initial population
            # or if we want to force reload the current one (might be redundant)
        elif db_files_data: # Auto-select the latest if no valid current selection or first population
            latest_db_filename = db_files_data[0]["filename"]
            self.db_var.set(latest_db_filename)
            self.logger.info(f"Auto-selecting latest DB: {latest_db_filename}")
            self.on_db_selected(latest_db_filename) # Trigger tag update for the auto-selected DB
        else: # Fallback, though covered by "if not db_files_data"
             self.logger.debug("No suitable DB files found after filtering and sorting.")
             self.db_var.set("Select Database...")
             self.on_db_selected("Select Database...") # Ensure UI updates if no DBs found


    def on_db_selected(self, db_filename: str):
        """
        Callback function triggered when a database file is selected from the dropdown.

        Sets `self.db_file` and calls `update_tag_list()` to populate the tag
        dropdown based on the schema of the selected database. If "Select Database..."
        is chosen, it clears the current selection and UI.

        Args:
            db_filename: The filename of the selected database (not the full path).
        """
        if db_filename == "Select Database..." or not db_filename:
            self.db_file = None
            self.tag_list = []
            self.tag_filter_dropdown.configure(values=["All"])
            self.tag_var.set("All") # Use tag_var
            self.clear_canvas() # Clear chart if no DB selected
            if self.loading_label: self.loading_label.destroy(); self.loading_label = None
            info_label = ctk.CTkLabel(self.chart_frame, text="Please select a database to view charts.", font=("Arial", 14))
            info_label.pack(padx=10, pady=20)
            self.logger.info("No database selected or selection cleared.")
            return
        
        self.db_file = os.path.join(PLC_LOGS_DIR, db_filename)
        self.logger.info(f"Database selected: {self.db_file}")
        self.update_tag_list()
        # Note: Chart is not automatically shown on DB selection; user must click "View Chart"
        # or have auto-refresh enabled.

    def update_tag_list(self):
        """
        Populates the tag filter dropdown based on the schema of the selected database file.

        Reads column names from the `plc_data` table (excluding standard columns like
        id, timestamp, source) and lists them as available tags. Auto-selects the
        first tag if available. Handles errors during database schema reading.
        """
        self.clear_canvas() # Clear previous chart/message before updating tags
        if self.loading_label: self.loading_label.destroy(); self.loading_label = None # Redundant due to clear_canvas

        if not self.db_file or not os.path.exists(self.db_file):
            self.tag_list = []
            self.tag_filter_dropdown.configure(values=["All"])
            self.tag_var.set("All")
            info_label = ctk.CTkLabel(self.chart_frame, text="Database not found or not accessible.", font=("Arial", 14))
            info_label.pack(padx=10, pady=20)
            self.logger.warning(f"Attempted to update tag list, but DB file not set or not found: {self.db_file}")
            return
        
        self.logger.debug(f"Updating tag list for DB: {self.db_file}")
        self.display_loading_indicator() # Show loading while fetching tags

        try:
            conn = sqlite3.connect(f"file:{self.db_file}?mode=ro", uri=True) # Open read-only
            cursor = conn.cursor()
            # Ensure we are querying the correct table name if it can vary.
            # For now, it's hardcoded as "plc_data" in various places.
            cursor.execute("PRAGMA table_info(plc_data);")
            columns = cursor.fetchall()
            tag_names = []
            for col in columns:
                name = col[1]
                # Exclude typical non-data columns
                if name.lower() not in ["id", "timestamp", "source", "index"]: # Added 'index' just in case
                    tag_names.append(name)
            conn.close()
            
            self.clear_loading_indicator() # Clear before updating UI

            self.tag_list = sorted(list(set(tag_names))) # Ensure unique and sorted tags
            self.logger.debug(f"Found {len(self.tag_list)} tags: {self.tag_list}")
            
            values = ["All"] + self.tag_list
            self.tag_filter_dropdown.configure(values=values)
            
            if self.tag_list: # If there are actual tags
                current_tag_selection = self.tag_var.get()
                if current_tag_selection in self.tag_list:
                    self.tag_var.set(current_tag_selection) # Keep valid selection
                    self.logger.debug(f"Kept existing valid tag selection: {current_tag_selection}")
                else:
                    self.tag_var.set(self.tag_list[0]) # Auto-select first tag
                    self.logger.info(f"Auto-selected first tag: {self.tag_list[0]}")
                # Potentially call show_chart() here if auto-refresh is on or if UX dictates immediate plot
            else: # No tags found
                self.tag_var.set("All")
                info_label = ctk.CTkLabel(self.chart_frame, text="No plottable tags found in the selected database.", font=("Arial", 14))
                info_label.pack(padx=10, pady=20)
                self.logger.info("No plottable tags found in DB.")

        except sqlite3.Error as e: # More specific exception
            self.clear_loading_indicator()
            self.logger.error(f"SQLite error reading schema from {self.db_file}: {e}", exc_info=True)
            messagebox.showerror("DB Schema Error", f"Failed to read database schema: {e}\nDB: {os.path.basename(self.db_file)}")
            self.tag_list = []
            self.tag_filter_dropdown.configure(values=["All"])
            self.tag_var.set("All")
        except Exception as e: # General fallback
            self.clear_loading_indicator()
            self.logger.error(f"Unexpected error updating tag list from {self.db_file}: {e}", exc_info=True)
            messagebox.showerror("Update Tag List Error", f"An unexpected error occurred: {e}")
            self.tag_list = []
            self.tag_filter_dropdown.configure(values=["All"])
            self.tag_var.set("All")


    def toggle_auto_refresh(self):
        """Toggles the auto-refresh state for the chart."""
        self.auto_refresh = not self.auto_refresh
        self.logger.info(f"Auto-refresh toggled {'on' if self.auto_refresh else 'off'}.")
        if self.auto_refresh:
            self.start_auto_refresh()

    def start_auto_refresh(self):
        """Initiates the auto-refresh process if enabled."""
        self.logger.debug("Starting auto-refresh scheduler.")
        self._schedule_auto_refresh()

    def _schedule_auto_refresh(self):
        """
        Internal method that periodically calls `show_chart()` if auto-refresh is active.
        The refresh interval is read from the UI.
        """
        if self.auto_refresh:
            self.logger.debug("Auto-refresh: Calling show_chart().")
            self.show_chart() # This will show loading indicator and start background worker
            try:
                interval_str = self.refresh_interval_entry.get()
                interval = float(interval_str)
                if interval < 1: 
                    interval = 1 # Minimum refresh interval 1 second
                    self.logger.warning(f"Refresh interval was < 1s, adjusted to 1s.")
                self.logger.debug(f"Scheduling next auto-refresh in {interval}s.")
            except ValueError:
                interval = 5 # Default interval if entry is invalid
                self.logger.warning(f"Invalid refresh interval '{interval_str}'. Defaulting to {interval}s.")
                self.refresh_interval_entry.delete(0, 'end')
                self.refresh_interval_entry.insert(0, str(interval))
            self.after(int(interval * 1000), self._schedule_auto_refresh)

    def show_chart(self):
        """
        Initiates the process of displaying a chart.

        It shows a loading indicator and starts a background thread
        (`_background_chart_worker`) to fetch and plot the data.
        """
        self.logger.info("View Chart button clicked or called (or by auto-refresh).")
        self.display_loading_indicator() # This will clear canvas first
        
        db_file = self.db_file
        tag = self.tag_var.get() # Use self.tag_var
        start_date = self.start_date_entry.get()
        end_date = self.end_date_entry.get()
        start_time = self.start_time_entry.get()
        end_time = self.end_time_entry.get()
        # Launch thread for query and plotting
        threading.Thread(
            target=self._background_chart_worker,
            args=(db_file, tag, start_date, end_date, start_time, end_time),
            daemon=True
        ).start()

    def display_loading_indicator(self):
        self.clear_canvas() # Ensure canvas is cleared before showing loading
        if not self.loading_label: # Create label if it doesn't exist
             self.loading_label = ctk.CTkLabel(self.chart_frame, text="Loading, please wait...", font=("Arial", 14, "italic"))
        self.loading_label.pack(padx=10, pady=20) # Pack (or re-pack) it
        self.chart_frame.update_idletasks() # Ensure it's displayed

    def clear_loading_indicator(self):
        """Hides the loading indicator label from the chart frame."""
        if self.loading_label:
            self.loading_label.pack_forget() 
        # self.loading_label = None # Keep if re-used, or destroy if created fresh each time

    def _background_chart_worker(self, db_file: str, tag_to_plot: str, 
                                 start_date: str, end_date: str, 
                                 start_time: str, end_time: str):
        """
        Worker function executed in a background thread to fetch and plot chart data.

        This prevents the GUI from freezing during database queries and chart rendering.
        Updates to the GUI (displaying the chart, error messages) are scheduled
        to run on the main thread using `self.after()`.

        Args:
            db_file: Full path to the SQLite database file.
            tag_to_plot: The name of the tag to plot. If "All", the first available
                         tag from `self.tag_list` is used.
            start_date: Start date string for filtering data (YYYY-MM-DD).
            end_date: End date string for filtering data (YYYY-MM-DD).
            start_time: Start time string for filtering data (HH:MM:SS).
            end_time: End time string for filtering data (HH:MM:SS).
        """
        self.logger.debug(f"Background chart worker started for DB: '{os.path.basename(db_file)}', Tag: '{tag_to_plot}'")
        
        self.after(0, self.clear_loading_indicator) # Schedule UI update on main thread

        if not db_file:
            self.logger.warning("Background chart worker: No database file provided.")
            self.after(0, lambda: self._chart_message("No database file selected. Please select a database from the dropdown.", "Info"))
            return

        effective_tag = tag_to_plot
        if tag_to_plot == "All":
            if self.tag_list: 
                effective_tag = self.tag_list[0]
                self.logger.info(f"Plotting 'All': Auto-selected first tag '{effective_tag}'")
            else:
                self.logger.warning("Plotting 'All' but no tags available in tag_list.")
                self.after(0, lambda: self._chart_message("No tags available to plot. Please select a database that contains tags.", "Info"))
                return
        
        if not effective_tag or effective_tag == "All": 
             self.logger.error(f"No specific tag selected or available for plotting. Tag: {effective_tag}")
             self.after(0, lambda: self._chart_message("No specific tag selected or available for plotting.", "Error"))
             return

        if not all(c.isalnum() or c == '_' for c in effective_tag): # Basic validation
            self.logger.error(f"Invalid tag name for plotting: {effective_tag}")
            self.after(0, lambda: self._chart_message(f"Invalid tag name: {effective_tag}. Tag names should be alphanumeric.", "Error"))
            return

        # Construct date filter for SQL query
        date_filter_parts = []
        query_params = []
        if start_date:
            start_dt_str = f"{start_date}{' ' + start_time if start_time else ' 00:00:00'}"
            date_filter_parts.append("timestamp >= ?")
            query_params.append(start_dt_str)
        if end_date:
            end_dt_str = f"{end_date}{' ' + end_time if end_time else ' 23:59:59'}"
            date_filter_parts.append("timestamp <= ?")
            query_params.append(end_dt_str)
        
        date_filter_sql = ""
        if date_filter_parts:
            date_filter_sql = " AND " + " AND ".join(date_filter_parts)
        
        self.logger.info(f"Plotting tag '{effective_tag}' from DB '{os.path.basename(db_file)}' with date filter: '{date_filter_sql if date_filter_sql else 'None'}'")
        
        try:
            conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True) # Read-only connection
            cursor = conn.cursor()
            
            # Securely construct query using placeholders for tag name is tricky with "Identifier"
            # For now, ensure effective_tag is sanitized.
            # Using f-string for column name, ensure `effective_tag` is validated (done above)
            query = f'SELECT timestamp, "{effective_tag}" FROM plc_data WHERE "{effective_tag}" IS NOT NULL{date_filter_sql} ORDER BY timestamp ASC'
            self.logger.debug(f"Executing query: {query} with params: {query_params}")
            cursor.execute(query, tuple(query_params))
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                self.logger.info(f"No data found for tag '{effective_tag}' with current filters.")
                self.after(0, lambda: self._chart_message(f"No data found for tag: '{effective_tag}' within the selected time range.", "Info"))
                return

            timestamps = [datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S") for r in rows]
            values = []
            conversion_warnings = 0
            for r_idx, r_val in enumerate(rows): # r_val is a tuple, e.g., (timestamp_str, value_from_db)
                try:
                    values.append(float(r_val[1]))
                except (ValueError, TypeError):
                    if conversion_warnings < 5: 
                        self.logger.warning(f"Could not convert value '{r_val[1]}' to float for tag '{effective_tag}' at timestamp '{rows[r_idx][0]}'. Skipping point.")
                    conversion_warnings += 1
            
            if conversion_warnings > 0:
                 self.logger.warning(f"Total of {conversion_warnings} data points could not be converted to float for tag '{effective_tag}'.")

            if not values: 
                 self.logger.info(f"No numeric data to plot for tag '{effective_tag}' after conversion attempts.")
                 self.after(0, lambda: self._chart_message(f"Data for tag '{effective_tag}' is not numeric or could not be converted.", "Info"))
                 return

            self.logger.debug(f"Plotting {len(values)} points for tag '{effective_tag}'.")
            fig = plt.Figure(figsize=(10, 4), tight_layout=True) 
            ax = fig.add_subplot(111)
            ax.plot(timestamps, values, marker='.', linestyle='-', markersize=4) 
            ax.set_title(f"Trend for {effective_tag}", fontsize=10)
            ax.set_xlabel("Time", fontsize=8)
            ax.set_ylabel(effective_tag, fontsize=8)
            ax.grid(True, which='both', linestyle='--', linewidth=0.5)
            ax.tick_params(axis='x', labelrotation=45, labelsize=8)
            ax.tick_params(axis='y', labelsize=8)
            
            self.after(0, lambda: self._display_chart_figure(fig))
        except sqlite3.OperationalError as oe: # Catch specific DB errors
            self.logger.error(f"Database error plotting tag '{effective_tag}': {oe}. Query: {query}", exc_info=True)
            self.after(0, lambda: self._chart_message(f"Database error plotting tag '{effective_tag}': {oe}. Check tag name and DB structure.", "Error"))
        except Exception as e: # Catch any other errors
            self.logger.error(f"Plot Error for tag '{effective_tag}': {e}", exc_info=True)
            self.after(0, lambda: self._chart_message(f"Plot Error for tag '{effective_tag}': {e}", "Error"))

    def _display_chart_figure(self, fig: plt.Figure):
        """
        Displays the generated Matplotlib figure on the Tkinter canvas.

        This method is called from the main thread via `self.after()`.

        Args:
            fig: The Matplotlib figure object to display.
        """
        self.logger.debug("Displaying new chart figure.")
        self.clear_canvas() 
        self.figure = fig
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

    def _chart_message(self, message: str, severity: str = "Info"):
        """
        Displays a message on the chart_frame or via a messagebox.

        Clears the canvas before showing the message. This method is called from
        the main thread via `self.after()`.

        Args:
            message: The message string to display.
            severity: "Info" to display on the chart_frame, "Error" to show a messagebox.
        """
        self.clear_canvas() 
        
        if severity == "Error":
            self.logger.error(f"Chart message (Error): {message}")
            messagebox.showerror("Chart Error", message)
        elif severity == "Info": # Includes "No Data" type messages
            self.logger.info(f"Chart message (Info): {message}")
            label = ctk.CTkLabel(self.chart_frame, text=message, font=("Arial", 12)) 
            label.pack(padx=10, pady=20)

    def clear_canvas(self):
        """
        Clears all widgets from the chart_frame, including any existing chart,
        loading label, or info messages. Resets `self.figure` and `self.canvas`.
        """
        self.logger.debug("Clearing chart canvas.")
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        self.figure = None 
        self.canvas = None 
        self.loading_label = None 

    def save_chart(self):
        """Saves the currently displayed chart to an image file (PNG, PDF, JPG)."""
        self.logger.info("Save chart button clicked.")
        if not self.figure:
            self.logger.warning("Save chart called but no chart figure exists.")
            messagebox.showerror("Error", "No chart to save. Generate a chart first.")
            return
        try:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG Image", "*.png"), ("PDF Document", "*.pdf"), ("JPEG Image", "*.jpg")]
            )
            if filepath:
                self.logger.info(f"Saving chart to: {filepath}")
                self.figure.savefig(filepath, dpi=300, bbox_inches='tight') 
                messagebox.showinfo("Chart Saved", f"Chart successfully saved to:\n{filepath}")
            else:
                self.logger.info("Save chart dialog cancelled by user.")
        except Exception as e:
            self.logger.error(f"Failed to save chart: {e}", exc_info=True)
            messagebox.showerror("Save Error", f"Failed to save chart: {e}")


    def export_chart_data(self):
        """
        Exports the data for the currently selected tag and time range to a CSV file.

        This re-queries the database based on the current UI filter settings.
        """
        self.logger.info("Export chart data button clicked.")
        db_filename = self.db_var.get() # This is just filename, self.db_file is full path
        if db_filename == "Select Database..." or not self.db_file: 
            self.logger.warning("Export chart data: No database selected.")
            messagebox.showerror("Export Error", "No database selected.")
            return

        tag_to_export = self.tag_var.get()
        if tag_to_export == "All":
            self.logger.info("Export chart data: 'All' tags selected, prompting user for specific tag.")
            messagebox.showinfo("Export Info", "Please select a specific tag to export its data.")
            return
        
        if not all(c.isalnum() or c == '_' for c in tag_to_export): 
            self.logger.error(f"Export chart data: Invalid tag name '{tag_to_export}'.")
            messagebox.showerror("Export Error", f"Invalid tag name for export: {tag_to_export}.")
            return

        start_date = self.start_date_entry.get()
        end_date = self.end_date_entry.get()
        start_time = self.start_time_entry.get()
        end_time = self.end_time_entry.get()
        date_filter = ""
        if start_date and start_time:
            date_filter += f" AND timestamp >= '{start_date} {start_time}'"
        elif start_date:
            date_filter += f" AND timestamp >= '{start_date} 00:00:00'"
        if end_date and end_time:
            date_filter += f" AND timestamp <= '{end_date} {end_time}'"
        elif end_date:
            date_filter += f" AND timestamp <= '{end_date} 23:59:59'"
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(f"SELECT timestamp, {tag} FROM plc_data WHERE {tag} IS NOT NULL{date_filter}")
            rows = cursor.fetchall()
            conn.close()
            export_file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if export_file:
                with open(export_file, "w", newline="") as f:
                    import csv
                    writer = csv.writer(f)
                    writer.writerow(["timestamp", "tag", "value"])
                    for r in rows:
                        writer.writerow([r[0], tag, r[1]])
                messagebox.showinfo("Exported", f"Data exported to {export_file}")
        except Exception as e:
            self.logger.error(f"Error exporting chart data for tag '{tag_to_export}': {e}", exc_info=True)
            messagebox.showerror("Export Error", f"An error occurred during export: {e}")
