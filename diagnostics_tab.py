import customtkinter as ctk
from datetime import datetime
from tkinter import END
from pyModbusTCP.client import ModbusClient

class DiagnosticsTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.ping_history = []
        self.error_messages = []
        self.success_count = 0
        self.fail_count = 0
        self.create_widgets()
        self.after(5000, self.update_diagnostics)

    def create_widgets(self):
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
        ip = self.app.global_settings.get("ip", "127.0.0.1")
        port = self.app.global_settings.get("port", 502)
        client = ModbusClient(host=ip, port=port, auto_open=True, timeout=2)

        start_time = datetime.now()
        try:
            result = client.read_coils(0, 1)
            success = result is not None
        except Exception as e:
            success = False
            self.error_messages.append(f"{datetime.now().strftime('%H:%M:%S')} - {str(e)}")

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
