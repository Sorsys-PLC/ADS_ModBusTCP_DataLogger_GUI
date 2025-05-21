import time
import json
from datetime import datetime
from pyModbusTCP.client import ModbusClient
from utils import initialize_db, log_to_db, load_config

client = None
tags = []
settings = {}

def get_uint32(registers, index):
    if index + 1 < len(registers):
        return (registers[index + 1] << 16) | registers[index]
    return None

def start_tcp_logging(stop_event=None, logger=None):
    global client, tags, settings

    config = load_config()
    tags = config.get("tags", [])
    settings = config.get("global_settings", {})

    ip = settings.get("ip", "192.168.0.10")
    port = settings.get("port", 502)
    delay = settings.get("polling_interval", 0.5)

    client = ModbusClient(host=ip, port=port, auto_open=True, timeout=5)
    initialize_db()

    if not client.open():
        msg = "Failed to connect to Modbus PLC."
        if logger: logger(msg)
        else: print(msg)
        return

    previous_trigger = False
    if logger: logger("Connected to Modbus PLC.")

    while not (stop_event and stop_event.is_set()):
        try:
            coils = client.read_coils(0, 100)
            registers = client.read_holding_registers(0, 200)

            if not coils or not registers:
                if logger: logger("Failed to read from PLC.")
                time.sleep(delay)
                continue

            current_trigger = coils[0] if len(coils) > 0 else False

            if not previous_trigger and current_trigger:
                row = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "Modbus"
                }

                for tag in tags:
                    if not tag.get("enabled", True):
                        continue
                    name = tag["name"].replace(" ", "_")
                    if tag["type"] == "coil":
                        val = coils[tag["address"]] if tag["address"] < len(coils) else None
                        row[name] = "ON" if val else "OFF"
                    elif tag["type"] == "register":
                        val = get_uint32(registers, tag["address"])
                        row[name] = round(val * tag.get("scale", 1.0), 4) if val is not None else None

                log_to_db(row)
                if logger: logger(f"Logged: {row}")

            previous_trigger = current_trigger
            time.sleep(delay)

        except Exception as e:
            if logger: logger(f"Logging error: {e}")
            break

    client.close()
    if logger: logger("Modbus logging stopped.")