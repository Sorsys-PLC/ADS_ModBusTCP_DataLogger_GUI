import customtkinter as ctk
import sqlite3
from tkinter import messagebox, filedialog
import matplotlib.pyplot as plt
from datetime import datetime
import csv

class ChartTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.chart_data = None
        self.init_ui()

    def init_ui(self):
        self.chart_button = ctk.CTkButton(self, text="View Chart", command=self.show_chart)
        self.chart_button.pack(pady=10)

        self.export_button = ctk.CTkButton(self, text="Export CSV", command=self.export_chart_data)
        self.export_button.pack(pady=10)

    def show_chart(self):
        if not self.app.db_file:
            messagebox.showerror("Error", "No database file found.")
            return

        try:
            conn = sqlite3.connect(self.app.db_file)
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({self.app.table_name})")
            columns = [col[1] for col in cursor.fetchall() if col[1] not in ('id', 'timestamp', 'source')]

            tag = self.app.tag_filter_dropdown.get()
            if tag == "All":
                messagebox.showerror("Error", "Please select a specific tag to plot.")
                return

            cursor.execute(f"SELECT timestamp, {tag} FROM {self.app.table_name} WHERE {tag} IS NOT NULL")
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                messagebox.showinfo("No Data", f"No data found for tag: {tag}")
                return

            timestamps = [datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S") for r in rows]
            values = [float(r[1]) for r in rows]

            plt.figure(figsize=(10, 4))
            plt.plot(timestamps, values, marker='o', linestyle='-')
            plt.title(f"Trend for {tag}")
            plt.xlabel("Time")
            plt.ylabel(tag)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.grid(True)
            plt.show()

        except Exception as e:
            messagebox.showerror("Plot Error", str(e))

    def export_chart_data(self):
        if not self.chart_data:
            messagebox.showerror("Error", "No chart data to export.")
            return

        export_file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if export_file:
            with open(export_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "tag", "value"])
                for t, v in self.chart_data:
                    writer.writerow([t.strftime("%Y-%m-%d %H:%M:%S"), tag, v])
            messagebox.showinfo("Exported", f"Data exported to {export_file}")
