import customtkinter as ctk
import json
import os
import hashlib
import sqlite3
import csv
import subprocess
import matplotlib.pyplot as plt
from datetime import datetime
from tkinter import messagebox, END, filedialog
from tag_configurator_tab import TagConfiguratorTab


CONFIG_FILE = "plc_logger_config.json"
DB_FOLDER = os.path.join(os.environ["USERPROFILE"], "Documents", "PLC_Logs")

from tkinter import ttk



class TagEditorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PLC Logger Configurator")
        self.geometry("1000x850")
        self.tags = []
        self.config_hash = None
        self.version = 1
        self.db_file = None
        self.table_name = "plc_data"
        self.auto_refresh = True

        self.global_settings = {
            "mode": "TCP",
            "ip": "192.168.0.10",
            "port": 502,
            "polling_interval": 0.5
        }

        self.create_widgets()
        self.load_config()
        self.find_latest_db()
        self.auto_refresh_loop()
        self.auto_refresh_chart()
    
    def update_tag_filter_dropdown(self):
        if hasattr(self, "tag_filter_dropdown"):
            tag_names = [tag["name"] for tag in self.tags] if self.tags else []
            self.tag_filter_dropdown.configure(values=["All"] + tag_names)
            self.tag_filter_dropdown.set("All")

    def create_widgets(self):
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        self.config_frame = ctk.CTkFrame(self.tabs)
        self.diagnostics_frame = ctk.CTkFrame(self.tabs)

        self.tabs.add(self.config_frame, text="Configuration")
        self.tabs.add(self.diagnostics_frame, text="Diagnostics")

        self.tag_configurator_frame = TagConfiguratorTab(self.tabs, self)
        self.tabs.add(self.tag_configurator_frame, text="Tag Configurator")

        self.create_config_tab()
        self.create_diagnostics_tab()

    def apply_tag_filter(self, value):
        pass  # placeholder until filter logic is implemented

    def toggle_auto_refresh(self):
        self.auto_refresh = not self.auto_refresh
        if self.auto_refresh:
            self.toggle_refresh_btn.configure(text="Pause Refresh")
        else:
            self.toggle_refresh_btn.configure(text="Resume Refresh")

    def open_db_location(self):
        if self.db_file and os.path.exists(self.db_file):
            folder = os.path.dirname(self.db_file)
            os.startfile(folder)
        else:
             messagebox.showwarning("Warning", "No database file found.")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    self.global_settings.update(config.get("global_settings", {}))
                    self.tags = config.get("tags", [])
            except Exception as e:
                messagebox.showwarning("Warning", f"Failed to load config: {e}")

    def find_latest_db(self):
        if not os.path.exists(DB_FOLDER):
            os.makedirs(DB_FOLDER)

        db_files = [f for f in os.listdir(DB_FOLDER) if f.endswith(".db")]
        if not db_files:
            self.db_file = None
            return

        db_files.sort(key=lambda f: os.path.getmtime(os.path.join(DB_FOLDER, f)), reverse=True)
        self.db_file = os.path.join(DB_FOLDER, db_files[0])

    def auto_refresh_loop(self):
        if self.auto_refresh:
            # Placeholder: put anything you'd like to auto-refresh (e.g. refresh data, update UI, etc.)
            pass
        self.after(5000, self.auto_refresh_loop)

    def create_config_tab(self):
        self.chart_auto_refresh = ctk.BooleanVar(value=False)
        self.chart_refresh_checkbox = ctk.CTkCheckBox(self.config_frame, text="Auto-Refresh Chart", variable=self.chart_auto_refresh)
        self.chart_refresh_checkbox.grid(row=1, column=13, padx=10, pady=10)
        self.chart_refresh_interval = ctk.CTkEntry(self.config_frame, placeholder_text="Refresh Interval (s)")
        self.chart_refresh_interval.insert(0, "5")
        self.chart_refresh_interval.grid(row=1, column=14, padx=10, pady=10)
        self.chart_refresh_status = ctk.CTkLabel(self.config_frame, text="")
        self.chart_refresh_status.grid(row=1, column=15, padx=10, pady=10)
        self.start_date_entry = ctk.CTkEntry(self.config_frame, placeholder_text="Start Date (YYYY-MM-DD)")
        self.start_date_entry.grid(row=1, column=4, padx=10, pady=10)

        self.end_date_entry = ctk.CTkEntry(self.config_frame, placeholder_text="End Date (YYYY-MM-DD)")
        self.end_date_entry.grid(row=1, column=5, padx=10, pady=10)

        self.multi_tag_checkbox = ctk.CTkCheckBox(self.config_frame, text="Compare All Tags")
        self.multi_tag_checkbox.grid(row=1, column=6, padx=10, pady=10)

        self.start_time_entry = ctk.CTkEntry(self.config_frame, placeholder_text="Start Time (HH:MM:SS)")
        self.start_time_entry.grid(row=1, column=7, padx=10, pady=10)

        self.end_time_entry = ctk.CTkEntry(self.config_frame, placeholder_text="End Time (HH:MM:SS)")
        self.end_time_entry.grid(row=1, column=8, padx=10, pady=10)

        self.save_chart_button = ctk.CTkButton(self.config_frame, text="Save Chart", command=self.save_chart)
        self.save_chart_button.grid(row=1, column=9, padx=10, pady=10)

        self.clear_pins_button = ctk.CTkButton(self.config_frame, text="Clear Pins", command=self.clear_annotations)
        self.clear_pins_button.grid(row=1, column=10, padx=10, pady=10)

        self.export_points_button = ctk.CTkButton(self.config_frame, text="Export Visible Points", command=self.export_chart_data)
        self.export_points_button.grid(row=1, column=11, padx=10, pady=10)

        self.chart_style_option = ctk.CTkOptionMenu(self.config_frame, values=["line", "scatter", "step"])
        self.chart_style_option.set("line")
        self.chart_style_option.grid(row=1, column=12, padx=10, pady=10)
        self.save_chart_button.grid(row=1, column=9, padx=10, pady=10)
        self.multi_tag_checkbox.grid(row=1, column=6, padx=10, pady=10)
        # Global settings
        self.mode_option = ctk.CTkOptionMenu(self.config_frame, values=["TCP", "ADS"])
        self.mode_option.set(self.global_settings["mode"])
        self.mode_option.grid(row=0, column=0, padx=10, pady=10)

        self.ip_entry = ctk.CTkEntry(self.config_frame, placeholder_text="IP Address")
        self.ip_entry.insert(0, self.global_settings["ip"])
        self.ip_entry.grid(row=0, column=1, padx=10, pady=10)

        self.port_entry = ctk.CTkEntry(self.config_frame, placeholder_text="Port")
        self.port_entry.insert(0, str(self.global_settings["port"]))
        self.port_entry.grid(row=0, column=2, padx=10, pady=10)

        self.polling_entry = ctk.CTkEntry(self.config_frame, placeholder_text="Polling Interval")
        self.polling_entry.insert(0, str(self.global_settings["polling_interval"]))
        self.polling_entry.grid(row=0, column=3, padx=10, pady=10)

        self.filter_entry = ctk.CTkEntry(self.config_frame, placeholder_text="Filter (tag name or keyword)")
        self.filter_entry.grid(row=0, column=4, padx=10, pady=10)

        self.tag_filter_dropdown = ctk.CTkOptionMenu(self.config_frame, values=["All"], command=self.apply_tag_filter)
        self.tag_filter_dropdown.set("All")
        self.tag_filter_dropdown.grid(row=1, column=0, padx=10, pady=10)

        self.toggle_refresh_btn = ctk.CTkButton(self.config_frame, text="Pause Refresh", command=self.toggle_auto_refresh)
        self.toggle_refresh_btn.grid(row=1, column=1, padx=10, pady=10)

        self.open_db_btn = ctk.CTkButton(self.config_frame, text="Open DB Location", command=self.open_db_location)
        self.open_db_btn.grid(row=1, column=2, padx=10, pady=10)

        self.chart_button = ctk.CTkButton(self.config_frame, text="View Chart", command=self.show_chart)
        self.chart_button.grid(row=1, column=3, padx=10, pady=10)

        # (The rest of your existing widgets remain unchanged)

    def create_diagnostics_tab(self):
        self.connection_status_label = ctk.CTkLabel(self.diagnostics_frame, text="Connection: Unknown")
        self.connection_status_label.pack(pady=10)

        self.last_ping_label = ctk.CTkLabel(self.diagnostics_frame, text="Last Ping: N/A")
        self.last_ping_label.pack(pady=5)

        self.success_rate_label = ctk.CTkLabel(self.diagnostics_frame, text="Read Success Rate: N/A")
        self.success_rate_label.pack(pady=5)

        self.error_log = ctk.CTkTextbox(self.diagnostics_frame, width=800, height=150)
        self.error_log.pack(pady=10)

        self.test_button = ctk.CTkButton(self.diagnostics_frame, text="Test Connection", command=self.test_connection)
        self.test_button.pack(pady=10)

        self.ping_history = []
        self.error_messages = []
        self.success_count = 0
        self.fail_count = 0

        self.after(5000, self.update_diagnostics)

    def update_diagnostics(self):
        from pyModbusTCP.client import ModbusClient

        ip = self.global_settings.get("ip", "127.0.0.1")
        port = self.global_settings.get("port", 502)
        client = ModbusClient(host=ip, port=port, auto_open=True, timeout=2)

        start_time = datetime.now()
        try:
            result = client.read_coils(0, 1)
            success = result is not None
        except Exception as e:
            success = False
            self.error_messages.append(f"{datetime.now().strftime('%H:%M:%S')} - {str(e)}")

        elapsed = (datetime.now() - start_time).total_seconds() * 1000  # ms
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

        total = self.success_count + self.fail_count
        if total > 0:
            rate = int((self.success_count / total) * 100)
            self.success_rate_label.configure(text=f"Read Success Rate: {rate}%")

        if self.error_messages:
            recent = "\n".join(self.error_messages[-5:])
            self.error_log.delete("1.0", END)
            self.error_log.insert("end", recent)

        self.after(5000, self.update_diagnostics)

    def test_connection(self):
        self.fail_count = 0
        self.success_count = 0
        self.error_messages.clear()
        self.update_diagnostics()

    def save_chart(self):
        if not hasattr(self, 'chart_data') or not self.chart_data:
            messagebox.showerror("Error", "No chart to save. Please view a chart first.")
            return
        fig, _ = self.chart_data
        filepath = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png"), ("PDF", "*.pdf")])
        if filepath:
            fig.savefig(filepath)
            messagebox.showinfo("Saved", f"Chart saved to {filepath}")

    def clear_annotations(self):
        if hasattr(self, 'chart_data'):
            fig, ax = self.chart_data
            for child in ax.get_children():
                if isinstance(child, plt.Annotation):
                    child.remove()
            fig.canvas.draw_idle()

    def export_chart_data(self):
        if not hasattr(self, 'chart_data') or not self.chart_data:
            messagebox.showerror("Error", "No chart data to export.")
            return
        fig, ax = self.chart_data
        export_file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if export_file:
            with open(export_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "tag", "value"])
                for line in ax.get_lines():
                    x, y = line.get_data()
                    for t, v in zip(x, y):
                        writer.writerow([t.strftime("%Y-%m-%d %H:%M:%S"), line.get_label(), v])
            messagebox.showinfo("Exported", f"Visible data exported to {export_file}")

    def auto_refresh_chart(self):
        interval = 5000
        try:
            interval = int(float(self.chart_refresh_interval.get()) * 1000)
        except:
            interval = 5000
        if self.chart_auto_refresh.get():
            self.show_chart(auto_call=True)
            self.chart_refresh_status.configure(text=f"Chart refreshed at {datetime.now().strftime('%H:%M:%S')}")
        self.after(interval, self.auto_refresh_chart)
          

    def show_chart(self, auto_call=False):
        self.chart_data = None
        if not self.db_file:
            messagebox.showerror("Error", "No database file found.")
            return

        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({self.table_name})")
            columns = [col[1] for col in cursor.fetchall() if col[1] not in ('id', 'timestamp', 'source')]

            start_date = self.start_date_entry.get()
            end_date = self.end_date_entry.get()
            start_time = self.start_time_entry.get()
            end_time = self.end_time_entry.get()

            date_filter = ""
            if start_date and start_time:
                start_dt = f"{start_date} {start_time}"
                date_filter += f" AND timestamp >= '{start_dt}'"
            elif start_date:
                date_filter += f" AND timestamp >= '{start_date} 00:00:00'"

            if end_date and end_time:
                end_dt = f"{end_date} {end_time}"
                date_filter += f" AND timestamp <= '{end_dt}'"
            elif end_date:
                date_filter += f" AND timestamp <= '{end_date} 23:59:59'"

            fig, ax = plt.subplots(figsize=(12, 5))
            if self.multi_tag_checkbox.get():
                for tag in columns:
                    cursor.execute(f"SELECT timestamp, {tag} FROM {self.table_name} WHERE {tag} IS NOT NULL{date_filter}")
                    rows = cursor.fetchall()
                    if not rows:
                        continue
                    timestamps = [datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S") for r in rows]
                    values = [float(r[1]) for r in rows]
                    style = self.chart_style_option.get()
                    if style == "scatter":
                        ax.scatter(timestamps, values, label=tag, picker=True)
                    elif style == "step":
                        ax.step(timestamps, values, label=tag, where="mid")
                    else:
                        ax.plot(timestamps, values, label=tag, picker=True)
                ax.legend()
                ax.set_title("Trends for All Tags")
            else:
                tag = self.tag_filter_dropdown.get()
                if tag == "All":
                    messagebox.showerror("Error", "Please select a specific tag or enable 'Compare All Tags'.")
                    return
                cursor.execute(f"SELECT timestamp, {tag} FROM {self.table_name} WHERE {tag} IS NOT NULL{date_filter}")
                rows = cursor.fetchall()
                if not rows:
                    messagebox.showinfo("No Data", f"No data found for tag: {tag}")
                    return
                timestamps = [datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S") for r in rows]
                values = [float(r[1]) for r in rows]
                style = self.chart_style_option.get()
                if style == "scatter":
                    ax.scatter(timestamps, values, label=tag, picker=True)
                elif style == "step":
                    ax.step(timestamps, values, label=tag, where="mid")
                else:
                    ax.plot(timestamps, values, label=tag, picker=True)
                ax.set_title(f"Trend for {tag}")

            ax.set_xlabel("Time")
            ax.set_ylabel("Value")
            ax.grid(True)
            plt.xticks(rotation=45)
            plt.tight_layout()
            fig.autofmt_xdate()
            fig.canvas.manager.set_window_title("Tag Chart")

            annot = ax.annotate("", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
                                bbox=dict(boxstyle="round", fc="w"), arrowprops=dict(arrowstyle="->"))
            annot.set_visible(False)

            def update_annot(line, ind):
                x, y = line.get_data()
                annot.xy = (x[ind[0]], y[ind[0]])
                text = (
                    f"Tag: {line.get_label()}\n"
                    f"Time: {x[ind[0]].strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Value: {y[ind[0]]:.2f}"
                )
                annot.set_text(text)
                annot.get_bbox_patch().set_alpha(0.9)

            def hover(event):
                vis = annot.get_visible()
                if event.inaxes == ax:
                    for line in ax.get_lines():
                        cont, ind = line.contains(event)
                        if cont:
                            update_annot(line, ind["ind"])
                            annot.set_visible(True)
                            fig.canvas.draw_idle()
                            return
                if vis:
                    annot.set_visible(False)
                    fig.canvas.draw_idle()

            def on_click(event):
                if event.inaxes == ax:
                    for line in ax.get_lines():
                        cont, ind = line.contains(event)
                        if cont:
                            update_annot(line, ind["ind"])
                            annot.set_visible(True)
                            fig.canvas.draw_idle()
                            return

            fig.canvas.mpl_connect("motion_notify_event", hover)
            fig.canvas.mpl_connect("button_press_event", on_click)
            self.chart_data = (plt.gcf(), plt.gca())
            plt.show()

        except Exception as e:
            messagebox.showerror("Plot Error", str(e))
        finally:
            cursor.close()
            conn.close()


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = TagEditorApp()
    app.mainloop()

