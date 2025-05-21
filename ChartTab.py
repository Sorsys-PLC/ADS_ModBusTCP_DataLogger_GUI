import customtkinter as ctk
from tkinter import messagebox, filedialog
import sqlite3
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
import threading

class ChartTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.auto_refresh = False
        self.refresh_thread = None
        self.canvas = None
        self.figure = None
        self.init_ui()

    def init_ui(self):
        self.start_date_entry = ctk.CTkEntry(self, placeholder_text="Start Date (YYYY-MM-DD)")
        self.start_date_entry.grid(row=0, column=0, padx=5, pady=5)

        self.end_date_entry = ctk.CTkEntry(self, placeholder_text="End Date (YYYY-MM-DD)")
        self.end_date_entry.grid(row=0, column=1, padx=5, pady=5)

        self.start_time_entry = ctk.CTkEntry(self, placeholder_text="Start Time (HH:MM:SS)")
        self.start_time_entry.grid(row=0, column=2, padx=5, pady=5)

        self.end_time_entry = ctk.CTkEntry(self, placeholder_text="End Time (HH:MM:SS)")
        self.end_time_entry.grid(row=0, column=3, padx=5, pady=5)

        self.refresh_interval_entry = ctk.CTkEntry(self, placeholder_text="Refresh Interval (s)")
        self.refresh_interval_entry.insert(0, "5")
        self.refresh_interval_entry.grid(row=0, column=4, padx=5, pady=5)

        self.auto_refresh_checkbox = ctk.CTkCheckBox(self, text="Auto Refresh", command=self.toggle_auto_refresh)
        self.auto_refresh_checkbox.grid(row=0, column=5, padx=5, pady=5)

        self.view_button = ctk.CTkButton(self, text="View Chart", command=self.show_chart)
        self.view_button.grid(row=1, column=0, columnspan=2, pady=10)

        self.save_button = ctk.CTkButton(self, text="Save Chart", command=self.save_chart)
        self.save_button.grid(row=1, column=2, padx=5, pady=10)

        self.export_button = ctk.CTkButton(self, text="Export CSV", command=self.export_chart_data)
        self.export_button.grid(row=1, column=3, padx=5, pady=10)

        self.chart_frame = ctk.CTkFrame(self)
        self.chart_frame.grid(row=2, column=0, columnspan=6, padx=10, pady=10, sticky="nsew")

    def toggle_auto_refresh(self):
        self.auto_refresh = not self.auto_refresh
        if self.auto_refresh:
            self.start_auto_refresh()

    def start_auto_refresh(self):
        def refresh_loop():
            while self.auto_refresh:
                self.show_chart()
                try:
                    interval = float(self.refresh_interval_entry.get())
                except ValueError:
                    interval = 5
                threading.Event().wait(interval)
        self.refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
        self.refresh_thread.start()

    def show_chart(self):
        if not self.app.db_file:
            messagebox.showerror("Error", "No database file found.")
            return

        tag = self.app.tag_filter_dropdown.get()
        if tag == "All":
            messagebox.showerror("Error", "Please select a specific tag to plot.")
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
            conn = sqlite3.connect(self.app.db_file)
            cursor = conn.cursor()
            cursor.execute(f"SELECT timestamp, {tag} FROM {self.app.table_name} WHERE {tag} IS NOT NULL{date_filter}")
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                messagebox.showinfo("No Data", f"No data found for tag: {tag}")
                return

            timestamps = [datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S") for r in rows]
            values = [float(r[1]) for r in rows]

            self.figure = plt.Figure(figsize=(10, 4))
            ax = self.figure.add_subplot(111)
            ax.plot(timestamps, values, marker='o', linestyle='-')
            ax.set_title(f"Trend for {tag}")
            ax.set_xlabel("Time")
            ax.set_ylabel(tag)
            ax.grid(True)
            self.clear_canvas()
            self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_frame)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill='both', expand=True)

        except Exception as e:
            messagebox.showerror("Plot Error", str(e))

    def clear_canvas(self):
        for widget in self.chart_frame.winfo_children():
            widget.destroy()

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

        tag = self.app.tag_filter_dropdown.get()
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
            conn = sqlite3.connect(self.app.db_file)
            cursor = conn.cursor()
            cursor.execute(f"SELECT timestamp, {tag} FROM {self.app.table_name} WHERE {tag} IS NOT NULL{date_filter}")
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
