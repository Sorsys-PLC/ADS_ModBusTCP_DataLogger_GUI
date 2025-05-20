import customtkinter as ctk
from tkinter import messagebox
from tag_configurator_tab import TagConfiguratorTab
from diagnostics_tab import DiagnosticsTab
from ChartTab import ChartTab
import subprocess
import os

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
        self.create_widgets()
        self.bind_tab_change()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def show_chart(self):
        from tkinter import messagebox
        messagebox.showinfo("Chart Viewer", "Chart viewer not yet connected.")

    def open_db_location(self):
        if self.db_file and os.path.exists(self.db_file):
            subprocess.Popen(f'explorer /select,"{self.db_file}"')
        else:
            from tkinter import messagebox
            messagebox.showerror("Database Not Found", "Database file path is not set or does not exist.")

    def toggle_auto_refresh(self):
        print("Auto refresh toggled (placeholder)")

    def create_widgets(self):
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
        self.tag_configurator_tab.pack(fill="both", expand=True)

    def update_tag_filter_dropdown(self):
        if hasattr(self, "chart_tab") and hasattr(self.chart_tab, "tag_filter_dropdown"):
            tag_names = [tag["name"] for tag in self.tags] if self.tags else []
            self.chart_tab.tag_filter_dropdown.configure(values=["All"] + tag_names)
            self.chart_tab.tag_filter_dropdown.set("All")


    def on_close(self):
        if hasattr(self, "tag_configurator_tab") and self.tag_configurator_tab.unsaved_changes:
            if messagebox.askyesno("Unsaved Changes", "You have unsaved tag changes. Save before exiting?"):
                self.tag_configurator_tab.save_tags()
        self.destroy()
    

    def bind_tab_change(self):
        self.tabs._segmented_button._command = self.on_tab_changed

    def on_tab_changed(self, tab_name):
        if hasattr(self, "tag_configurator_tab") and self.tag_configurator_tab.unsaved_changes:
            if not messagebox.askyesno("Unsaved Changes", "You have unsaved tag changes. Switch tabs without saving?"):
                self.tabs.set("Tag Configurator")  # <- safely switch back
                return
        self.tabs.set(tab_name)  # <- safely switch to the requested tab

    