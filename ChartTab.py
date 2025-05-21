import customtkinter as ctk
from tkinter import messagebox, filedialog
import sqlite3
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
import threading
import os

PLC_LOGS_DIR = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Documents", "PLC_Logs")

class ChartTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
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
        self.db_var = ctk.StringVar(value="")
        self.db_dropdown = ctk.CTkOptionMenu(self, variable=self.db_var, values=[], command=self.on_db_selected)
        self.db_dropdown.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.db_dropdown.configure(width=320)
        self.db_dropdown.set("Select Database...")

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
        if not os.path.exists(PLC_LOGS_DIR):
            os.makedirs(PLC_LOGS_DIR, exist_ok=True)
        db_files = [f for f in os.listdir(PLC_LOGS_DIR) if f.lower().endswith(".db")]
        values = ["Select Database..."] + db_files
        self.db_dropdown.configure(values=values)
        if db_files:
            self.db_dropdown.set(db_files[0])
            self.on_db_selected(db_files[0])

    def on_db_selected(self, db_file):
        if db_file == "Select Database...":
            self.db_file = None
            self.tag_list = []
            self.tag_filter_dropdown.configure(values=["All"])
            self.tag_filter_dropdown.set("All")
            return
        self.db_file = os.path.join(PLC_LOGS_DIR, db_file)
        self.update_tag_list()

    def update_tag_list(self):
        if not self.db_file or not os.path.exists(self.db_file):
            self.tag_list = []
            self.tag_filter_dropdown.configure(values=["All"])
            self.tag_filter_dropdown.set("All")
            return
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(plc_data);")
            columns = cursor.fetchall()
            tag_names = []
            for col in columns:
                name = col[1]
                if name not in ["id", "timestamp", "source"]:
                    tag_names.append(name)
            conn.close()
            self.tag_list = tag_names
            values = ["All"] + tag_names
            self.tag_filter_dropdown.configure(values=values)
            if tag_names:
                self.tag_filter_dropdown.set(tag_names[0])
            else:
                self.tag_filter_dropdown.set("All")
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to read DB schema: {e}")
            self.tag_list = []
            self.tag_filter_dropdown.configure(values=["All"])
            self.tag_filter_dropdown.set("All")

    def toggle_auto_refresh(self):
        self.auto_refresh = not self.auto_refresh
        if self.auto_refresh:
            self.start_auto_refresh()

    def start_auto_refresh(self):
        self._schedule_auto_refresh()

    def _schedule_auto_refresh(self):
        if self.auto_refresh:
            self.show_chart()
            try:
                interval = float(self.refresh_interval_entry.get())
            except ValueError:
                interval = 5
            self.after(int(interval * 1000), self._schedule_auto_refresh)

    def show_chart(self):
        # Show a loading label
        self.display_loading_indicator()
        # Gather current UI parameters
        db_file = self.db_file
        tag = self.tag_filter_dropdown.get()
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
        self.clear_canvas()
        self.loading_label = ctk.CTkLabel(self.chart_frame, text="Loading chart, please wait...", font=("Arial", 14, "italic"))
        self.loading_label.pack(padx=10, pady=20)

    def _background_chart_worker(self, db_file, tag, start_date, end_date, start_time, end_time):
        # This runs in a background thread!
        if not db_file:
            self.after(0, lambda: self._chart_error("No database file selected."))
            return
        if tag == "All":
            self.after(0, lambda: self._chart_error("Please select a specific tag to plot."))
            return
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
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute(f"SELECT timestamp, {tag} FROM plc_data WHERE {tag} IS NOT NULL{date_filter}")
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                self.after(0, lambda: self._chart_info(f"No data found for tag: {tag}"))
                return

            timestamps = [datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S") for r in rows]
            values = [float(r[1]) for r in rows]

            fig = plt.Figure(figsize=(10, 4))
            ax = fig.add_subplot(111)
            ax.plot(timestamps, values, marker='o', linestyle='-')
            ax.set_title(f"Trend for {tag}")
            ax.set_xlabel("Time")
            ax.set_ylabel(tag)
            ax.grid(True)
            self.after(0, lambda: self._display_chart_figure(fig))
        except Exception as e:
            self.after(0, lambda: self._chart_error(f"Plot Error: {e}"))

    def _display_chart_figure(self, fig):
        self.clear_canvas()
        self.figure = fig
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

    def _chart_error(self, message):
        self.clear_canvas()
        messagebox.showerror("Chart Error", message)

    def _chart_info(self, message):
        self.clear_canvas()
        messagebox.showinfo("No Data", message)

    def clear_canvas(self):
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        self.loading_label = None

    def save_chart(self):
        if not self.figure:
            messagebox.showerror("Error", "No chart to save.")
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png"), ("PDF", "*.pdf")])
        if filepath:
            self.figure.savefig(filepath)
            messagebox.showinfo("Saved", f"Chart saved to {filepath}")

    def export_chart_data(self):
        if not self.figure:
            messagebox.showerror("Error", "No chart data to export.")
            return
        tag = self.tag_filter_dropdown.get()
        if tag == "All":
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
            messagebox.showerror("Export Error", str(e))
