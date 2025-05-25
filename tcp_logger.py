import time
import json
from datetime import datetime
from pyModbusTCP.client import ModbusClient
from utils import initialize_db, DBLogger, load_config, DB_PATH
import utils
import threading


client = None
tags = []
settings = {}

# Constants for reconnection logic
MAX_RETRIES = 5
RETRY_DELAY = 10  # seconds

def get_uint32(registers: list[int], index: int) -> int | None:
    """
    Extracts a 32-bit unsigned integer from a list of 16-bit registers.

    Assumes little-endian format (second register is high word).

    Args:
        registers: A list of 16-bit integer values from the Modbus device.
        index: The starting index in the `registers` list for the 32-bit value.
               Two registers starting from this index will be used.

    Returns:
        The combined 32-bit unsigned integer, or None if the index is out of bounds.
    """
    if index + 1 < len(registers):
        # registers[index] is low word, registers[index+1] is high word
        return (registers[index + 1] << 16) | registers[index]
    return None

def start_tcp_logging(stop_event: threading.Event = None, logger: callable = None):
    """
    Starts the Modbus TCP logging process in a loop.

    This function connects to a Modbus TCP PLC, reads configured tags,
    and logs data to an SQLite database when a trigger condition is met.
    It includes reconnection logic in case of communication failures.

    The logging process continues until the `stop_event` is set.

    Args:
        stop_event: A `threading.Event` object that signals the logging loop to stop.
        logger: A logging function (e.g., from `gui_main._get_composite_logger`)
                that accepts a message string and an optional logging level.
                This logger is used for all operational messages from this worker.
    """
    global client, tags, settings
    import logging # Ensure logging module is available for levels

    # Helper function to log messages using the passed-in logger
    def _log_worker_message(message, level=logging.INFO, exc_info=False):
        # The passed 'logger' is expected to be the composite logger from gui_main,
        # which handles GUI updates and central logging.
        # The message here should be the core message. The composite logger handles timestamping/formatting.
        # Adding a prefix here if we want to distinguish worker messages further,
        # though module name will be in central log.
        log_msg_with_prefix = f"[TCP_WORKER] {message}"
        if logger:
            logger(log_msg_with_prefix, level=level) # Pass level to the composite logger
        else:
            # Fallback if no logger is provided (e.g., direct script run without proper setup)
            print(f"NO_LOGGER: {log_msg_with_prefix}")

    db_logger = None
    try:
        _log_worker_message("Initializing TCP logging worker...", level=logging.DEBUG)
        config = load_config()
        tags = config.get("tags", [])
        settings = config.get("global_settings", {})

        ip = settings.get("ip", "192.168.0.10")
        port = settings.get("port", 502)
        delay = settings.get("polling_interval", 0.5) # This is the PLC polling delay

        _log_worker_message(f"Attempting to connect to Modbus PLC at {ip}:{port}", level=logging.INFO)
        client = ModbusClient(host=ip, port=port, auto_open=False, timeout=5) # auto_open=False for manual control
        
        # initialize_db() is called in gui_main before starting the thread.
        # DB_PATH should be valid if we reach here.
        if not utils.DB_PATH:
            _log_worker_message("DB_PATH is not set. Cannot proceed with DB operations.", level=logging.ERROR)
            return # Critical error, cannot log to DB.
            
        _log_worker_message(f"Using database file: {DB_PATH}", level=logging.DEBUG)

        db_logger = DBLogger(DB_PATH) # DB_PATH is now from utils directly
        try:
            db_logger.open()
            _log_worker_message("Database connection opened successfully for worker.", level=logging.DEBUG)
        except Exception as e:
            _log_worker_message(f"Error opening DB for worker: {e}", level=logging.ERROR, exc_info=True)
            if client and client.is_open: # Though client might not be open yet
                client.close()
            return

        previous_trigger = False
        retries = 0
        
        _log_worker_message("Starting main Modbus logging loop.", level=logging.INFO)
        
        main_loop_active = True
        while main_loop_active and not (stop_event and stop_event.is_set()):
            try:
                if not client.is_open:
                    _log_worker_message(f"PLC connection lost or not established. Attempting to (re)connect to {ip}:{port}...", level=logging.WARNING)
                    if not client.open():
                        # Raise connection error to be caught by the specific handler below
                        raise ConnectionError(f"Failed to connect to PLC at {ip}:{port} after explicit attempt.")
                    _log_worker_message(f"Successfully (re)connected to Modbus PLC at {ip}:{port}.", level=logging.INFO)
                    retries = 0 # Reset retries on successful connection

                # --- Read from PLC ---
                coils = None
                registers = None
                try:
                    coils = client.read_coils(0, 100)
                    registers = client.read_holding_registers(0, 125)
                except Exception as read_exc: 
                    _log_worker_message(f"Error reading from PLC: {read_exc}. Attempting to reconnect.", level=logging.ERROR)
                    if client.is_open:
                        client.close()
                    # This will make coils/registers None, triggering reconnection logic below

                if not coils or not registers:
                    if client.is_open: # If it was open, the read failed
                        _log_worker_message("Failed to read from PLC (coils or registers are None/empty). Closing connection before retry.", level=logging.WARNING)
                        client.close() # Close before retry attempt

                    # --- Reconnection Logic ---
                    if retries < MAX_RETRIES:
                        retries += 1
                        _log_worker_message(f"Reconnection attempt {retries}/{MAX_RETRIES} in {RETRY_DELAY} seconds...", level=logging.WARNING)
                        if stop_event and stop_event.wait(RETRY_DELAY): break # Exit if stop_event is set during wait
                        elif not stop_event: time.sleep(RETRY_DELAY)
                        continue # Retry connecting and reading in the next iteration of the main loop
                    else:
                        _log_worker_message(f"Max reconnection attempts ({MAX_RETRIES}) reached. Stopping TCP logging worker.", level=logging.ERROR)
                        main_loop_active = False # Exit main loop
                        continue # To end the loop

                retries = 0 # Reset retries on successful read

                # --- Process Data ---
                current_trigger = coils[0] if len(coils) > 0 else False
                if not previous_trigger and current_trigger:
                    row = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "Modbus"
                    }
                    for tag_conf in tags: 
                        if not tag_conf.get("enabled", True):
                            continue
                        name = tag_conf["name"].replace(" ", "_")
                        tag_type = tag_conf["type"].lower()
                        address = tag_conf["address"]
                        
                        val = None
                        if tag_type == "coil":
                            if address < len(coils):
                                val = coils[address]
                                row[name] = "ON" if val else "OFF"
                            else:
                                _log_worker_message(f"Coil address {address} for tag '{name}' out of range (max: {len(coils)-1}).", level=logging.WARNING)
                                row[name] = None
                        elif tag_type == "register":
                            val_raw = get_uint32(registers, address)
                            if val_raw is not None:
                                row[name] = round(val_raw * tag_conf.get("scale", 1.0), 4)
                            else:
                                _log_worker_message(f"Register address {address} for tag '{name}' out of range for get_uint32 (max: {len(registers)-2}).", level=logging.WARNING)
                                row[name] = None
                        else:
                             _log_worker_message(f"Unknown tag type '{tag_type}' for tag '{name}'.", level=logging.WARNING)
                             row[name] = None
                    
                    db_logger.log("plc_data", row) # This uses central logging via DBLogger's own logger
                    _log_worker_message(f"Logged data: {row}", level=logging.DEBUG)

                previous_trigger = current_trigger
                if stop_event and stop_event.wait(delay): break # Exit if stop_event is set during wait
                elif not stop_event: time.sleep(delay)


            except ConnectionError as ce: 
                _log_worker_message(f"Connection error: {ce}", level=logging.ERROR)
                if client and client.is_open: # Should be closed already if client.open() failed, but check anyway
                    client.close()
                
                if retries < MAX_RETRIES:
                    retries += 1
                    _log_worker_message(f"Connection attempt {retries}/{MAX_RETRIES} will be made in {RETRY_DELAY} seconds...", level=logging.WARNING)
                    if stop_event and stop_event.wait(RETRY_DELAY): break
                    elif not stop_event: time.sleep(RETRY_DELAY)
                else:
                    _log_worker_message(f"Max connection attempts ({MAX_RETRIES}) reached after ConnectionError. Stopping TCP logging worker.", level=logging.ERROR)
                    main_loop_active = False
            except Exception as e: 
                _log_worker_message(f"Unexpected error in Modbus logging loop: {e}", level=logging.CRITICAL, exc_info=True)
                # Depending on the error, might want to attempt reconnection or just stop
                # For now, let's try to continue if not a connection error, but log it.
                if stop_event and stop_event.wait(RETRY_DELAY): break
                elif not stop_event: time.sleep(RETRY_DELAY) # Wait before trying again or exiting


        # --- End of Main Loop ---
        _log_worker_message("Exited main Modbus logging loop.", level=logging.INFO)

    except Exception as e: 
        _log_worker_message(f"Fatal error in start_tcp_logging setup: {e}", level=logging.CRITICAL, exc_info=True)
    finally:
        if db_logger is not None and getattr(db_logger, "conn", None):
            db_logger.close()
            _log_worker_message("Database connection closed by worker.", level=logging.DEBUG)
        if client and client.is_open:
            client.close()
            _log_worker_message("Modbus client connection closed by worker.", level=logging.DEBUG)
        _log_worker_message("Modbus TCP logging worker finished.", level=logging.INFO)
