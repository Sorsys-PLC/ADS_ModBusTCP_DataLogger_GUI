import customtkinter as ctk

class ConfigTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.create_widgets()

    def create_widgets(self):
        self.mode_option = ctk.CTkOptionMenu(self, values=["TCP", "ADS"])
        self.mode_option.set(self.app.global_settings["mode"])
        self.mode_option.grid(row=0, column=0, padx=10, pady=10)

        self.ip_entry = ctk.CTkEntry(self, placeholder_text="IP Address")
        self.ip_entry.insert(0, self.app.global_settings["ip"])
        self.ip_entry.grid(row=0, column=1, padx=10, pady=10)

        self.port_entry = ctk.CTkEntry(self, placeholder_text="Port")
        self.port_entry.insert(0, str(self.app.global_settings["port"]))
        self.port_entry.grid(row=0, column=2, padx=10, pady=10)

        self.polling_entry = ctk.CTkEntry(self, placeholder_text="Polling Interval")
        self.polling_entry.insert(0, str(self.app.global_settings["polling_interval"]))
        self.polling_entry.grid(row=0, column=3, padx=10, pady=10)

        self.filter_entry = ctk.CTkEntry(self, placeholder_text="Filter (tag name or keyword)")
        self.filter_entry.grid(row=0, column=4, padx=10, pady=10)

        self.tag_filter_dropdown = ctk.CTkOptionMenu(self, values=["All"], command=self.app.update_tag_filter_dropdown)
        self.tag_filter_dropdown.set("All")
        self.tag_filter_dropdown.grid(row=1, column=0, padx=10, pady=10)

        self.toggle_refresh_btn = ctk.CTkButton(self, text="Pause Refresh", command=self.app.toggle_auto_refresh)
        self.toggle_refresh_btn.grid(row=1, column=1, padx=10, pady=10)

        self.open_db_btn = ctk.CTkButton(self, text="Open DB Location", command=self.app.open_db_location)
        self.open_db_btn.grid(row=1, column=2, padx=10, pady=10)

        self.chart_button = ctk.CTkButton(self, text="View Chart", command=self.app.show_chart)
        self.chart_button.grid(row=1, column=3, padx=10, pady=10)
