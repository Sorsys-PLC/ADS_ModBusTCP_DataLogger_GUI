import time
import json
from datetime import datetime
from pyModbusTCP.client import ModbusClient
from utils import initialize_db, DBLogger, load_config, DB_PATH

client = None
tags = []
settings = {}

def get_uint32(registers, index):
    if index + 1 < len(registers):
        return (registers[index + 1] << 16) | registers[index]
    return None

def start_tcp_logging(stop_event=None, logger=None):
    global client, tags, settings

    try:
        config = load_config()
        tags = config.get("tags", [])
        settings = config.get("global_settings", {})

        ip = settings.get("ip", "192.168.0.10")
        port = settings.get("port", 502)
        delay = settings.get("polling_interval", 0.5)

        msg = f"[tcp_logger] Attempting to connect to Modbus PLC at {ip}:{port}"
        print(msg)
        if logger: logger(msg)

        client = ModbusClient(host=ip, port=port, auto_open=True, timeout=5)
        initialize_db()

        db_file = DB_PATH
        print(f"Logging to database file: {db_file}")
        if logger: logger(f"Logging to database file: {db_file}")

        if not client.open():
            msg = f"Failed to connect to Modbus PLC at {ip}:{port}"
            print(msg)
            if logger: logger(msg)
            return

        previous_trigger = False
        msg = f"Connected to Modbus PLC at {ip}:{port}."
        print(msg)
        if logger: logger(msg)

        db_logger = DBLogger(db_file)
        try:
            db_logger.open()
            msg = "Database connection opened successfully."
            print(msg)
            if logger: logger(msg)
        except Exception as e:
            err_msg = f"Error opening DB: {e}"
            print(err_msg)
            if logger: logger(err_msg)
            client.close()
            return

        msg = "Starting main Modbus logging loop."
        print(msg)
        if logger: logger(msg)

        try:
            while not (stop_event and stop_event.is_set()):
                try:
                    coils = client.read_coils(0, 100)
                    registers = client.read_holding_registers(0, 125)

                    if not coils or not registers:
                        msg = "Failed to read from PLC. Coils or registers are None or empty."
                        print(msg)
                        if logger: logger(msg)
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
                            tag_type = tag["type"].lower()
                            if tag_type == "coil":
                                val = coils[tag["address"]] if tag["address"] < len(coils) else None
                                row[name] = "ON" if val else "OFF"
                            elif tag_type == "register":
                                val = get_uint32(registers, tag["address"])
                                row[name] = round(val * tag.get("scale", 1.0), 4) if val is not None else None

                        db_logger.log("plc_data", row)
                        log_msg = f"Logged: {row}"
                        print(log_msg)
                        if logger: logger(log_msg)

                    previous_trigger = current_trigger
                    time.sleep(delay)

                except Exception as e:
                    err_msg = f"Logging error in main loop: {e}"
                    print(err_msg)
                    if logger: logger(err_msg)
                    break
        finally:
            db_logger.close()
            client.close()
            msg = "Modbus logging stopped."
            print(msg)
            if logger: logger(msg)

    except Exception as e:
        fatal_msg = f"Fatal error in start_tcp_logging: {e}"
        print(fatal_msg)
        if logger: logger(fatal_msg)
