import pyads
import time
from datetime import datetime
from utils import log_to_db, load_config # Added load_config import
from pyads import ADSError

# Removed old hardcoded constants:
# ADS_PLC_AMS_ID = "5.132.118.239.1.1"
# ADS_PORT = 851
# ADS_PLC_IP = "192.168.0.1"
# ADS_POLLING_DELAY = 0.5
import logging # Ensure logging module is available for levels

# Helper function for logging within this worker
def _log_worker_message(logger_func: callable | None, message: str, level: int = logging.INFO, exc_info: bool = False):
    """
    Logs a message using the provided logger function, prefixing it with "[ADS_WORKER]".

    Args:
        logger_func: The logger function (e.g., from `gui_main._get_composite_logger`)
                     to use for logging.
        message: The message string to log.
        level: The logging level (e.g., `logging.INFO`).
        exc_info: Whether to include exception information in the log.
    """
    log_msg_with_prefix = f"[ADS_WORKER] {message}"
    if logger_func:
        # Assuming logger_func from gui_main's _get_composite_logger can handle exc_info if passed via self.logger.log
        # However, the current composite logger in gui_main does not explicitly pass exc_info.
        # For simplicity, we'll rely on the central logger (called by self.log_message in gui_main)
        # to handle exc_info if the level is ERROR or CRITICAL.
        # If direct exc_info passing to composite_log_func is needed, its signature would need change.
        logger_func(log_msg_with_prefix, level=level) 
    else:
        # Fallback if no logger is provided (e.g., direct script run without proper setup)
        print(f"NO_LOGGER ({logging.getLevelName(level)}): {log_msg_with_prefix}")
        if exc_info:
            import traceback
            traceback.print_exc()


def safe_read_by_name(plc: pyads.Connection, 
                      symbol: str, 
                      plctype: int, 
                      default_value=None, 
                      logger_func: callable | None = None, 
                      tag_name_for_log: str = ""):
    """
    Safely reads a symbol from the ADS device by its name.

    Catches `pyads.ADSError` and other exceptions during the read operation,
    logs them if a logger is provided, and returns a default value.

    Args:
        plc: The `pyads.Connection` object.
        symbol: The name of the symbol to read (e.g., "GVL.myVariable").
        plctype: The `pyads.PLCTYPE_` constant representing the data type.
        default_value: The value to return if the read fails. Defaults to None.
        logger_func: Optional logger function for logging errors.
        tag_name_for_log: Optional descriptive name for the tag/symbol, used in log messages.

    Returns:
        The value read from the PLC, or `default_value` if an error occurs.
    """
    try:
        return plc.read_by_name(symbol, plctype)
    except ADSError as e:
        if logger_func:
            _log_worker_message(logger_func, f"ADSError reading symbol '{symbol}' (Tag: '{tag_name_for_log}'): {e}. Using default: {default_value}", level=logging.WARNING)
        return default_value
    except Exception as e: 
        if logger_func:
            _log_worker_message(logger_func, f"Unexpected error reading symbol '{symbol}' (Tag: '{tag_name_for_log}'): {e}. Using default: {default_value}", level=logging.ERROR, exc_info=True)
        return default_value


def start_ads_data_pull(stop_event: threading.Event = None, logger: callable = None):
    """
    Starts the Beckhoff ADS data pulling process.

    This function connects to an ADS-enabled PLC using pyads, reads a predefined
    set of PLC variables (symbols) when a trigger condition is met, and logs this
    data to an SQLite database. The process runs in a loop until the `stop_event`
    is set.

    The specific symbols read are hardcoded in this version and correspond to
    particular data structures expected on the PLC (e.g., "GV.SelPartName",
    "Inspection.CAM_CycleGoodCNT", "Packaging.TotalBad_1CNT").

    Args:
        stop_event: A `threading.Event` to signal when to stop the logging loop.
        logger: A logging function (e.g., from `gui_main._get_composite_logger`)
                for operational messages from this worker.
    """
    _log_worker_message(logger, "Initializing ADS data pull worker...", level=logging.DEBUG)
    config = load_config() # This uses its own logging for errors, if any
    global_settings = config.get("global_settings", {})
    
    ams_net_id_val = global_settings.get("ams_net_id", "5.132.118.239.1.1")
    ams_port_val = global_settings.get("ams_port", 851)
    plc_ip_val = global_settings.get("ip", "192.168.0.1") 
    polling_delay_val = global_settings.get("polling_interval", 0.5)

    _log_worker_message(logger, f"ADS Configuration: AMS Net ID='{ams_net_id_val}', AMS Port={ams_port_val}, PLC IP='{plc_ip_val}', Polling Interval={polling_delay_val}s", level=logging.INFO)

    # Initialize PLC connection (consider retry logic here as well, similar to TCP)
    plc = None
    try:
        _log_worker_message(logger, f"Attempting to connect to ADS PLC: {ams_net_id_val} at {plc_ip_val}:{ams_port_val}", level=logging.INFO)
        plc = pyads.Connection(ams_net_id_val, ams_port_val, plc_ip_val)
        plc.open()
        _log_worker_message(logger, "Successfully connected to ADS PLC.", level=logging.INFO)
    except pyads.ADSError as e:
        _log_worker_message(logger, f"ADS Connection Error: {e}. Could not connect to PLC.", level=logging.ERROR, exc_info=True)
        return # Cannot proceed without PLC connection
    except Exception as e: # Catch other potential errors like routing issues
        _log_worker_message(logger, f"Failed to connect to ADS PLC due to unexpected error: {e}", level=logging.ERROR, exc_info=True)
        return

    previous_coil_state = False
    _log_worker_message(logger, "Starting main ADS data logging loop.", level=logging.INFO)

    while not (stop_event and stop_event.is_set()):
        try:
            # Pass the logger to safe_read_by_name
            srbn_logger = lambda msg, level, exc_info=False: _log_worker_message(logger, msg, level, exc_info)

            coil1_state = safe_read_by_name(plc, "MessageToHMI.dataLogTrg", pyads.PLCTYPE_BOOL, False, logger_func=srbn_logger, tag_name_for_log="TriggerCoil")

            if not previous_coil_state and coil1_state:
                _log_worker_message(logger, "Trigger detected. Reading data from ADS PLC.", level=logging.DEBUG)
                active_part = safe_read_by_name(plc, "GV.SelPartName", pyads.PLCTYPE_WSTRING, "N/A", logger_func=srbn_logger, tag_name_for_log="ActivePart")
                lot_number = safe_read_by_name(plc, "GV.ActiveLotNumber", pyads.PLCTYPE_WSTRING, "N/A", logger_func=srbn_logger, tag_name_for_log="LotNumber")
                operator_name = safe_read_by_name(plc, "GV.ActiveOperatorName", pyads.PLCTYPE_WSTRING, "N/A", logger_func=srbn_logger, tag_name_for_log="OperatorName")

                cam_data = {
                    "CAM1_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[0].Count", pyads.PLCTYPE_DWORD, 0, logger_func=srbn_logger, tag_name_for_log="CAM1_LR_Good"),
                    "CAM2_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[1].Count", pyads.PLCTYPE_DWORD, 0, logger_func=srbn_logger, tag_name_for_log="CAM2_LR_Good"),
                    "CAM3_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[2].Count", pyads.PLCTYPE_DWORD, 0, logger_func=srbn_logger, tag_name_for_log="CAM3_LR_Good"),
                    "CAM4_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[3].Count", pyads.PLCTYPE_DWORD, 0, logger_func=srbn_logger, tag_name_for_log="CAM4_LR_Good"),
                    "CAM5_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[4].Count", pyads.PLCTYPE_DWORD, 0, logger_func=srbn_logger, tag_name_for_log="CAM5_LR_Good"),
                    "CAM6_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[5].Count", pyads.PLCTYPE_DWORD, 0, logger_func=srbn_logger, tag_name_for_log="CAM6_LR_Good"),
                    "CAM1_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[0].Count", pyads.PLCTYPE_DWORD, 0, logger_func=srbn_logger, tag_name_for_log="CAM1_B_Good"),
                    "CAM2_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[1].Count", pyads.PLCTYPE_DWORD, 0, logger_func=srbn_logger, tag_name_for_log="CAM2_B_Good"),
                    "CAM3_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[2].Count", pyads.PLCTYPE_DWORD, 0, logger_func=srbn_logger, tag_name_for_log="CAM3_B_Good"),
                    "CAM4_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[3].Count", pyads.PLCTYPE_DWORD, 0, logger_func=srbn_logger, tag_name_for_log="CAM4_B_Good"),
                    "CAM5_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[4].Count", pyads.PLCTYPE_DWORD, 0, logger_func=srbn_logger, tag_name_for_log="CAM5_B_Good"),
                    "CAM6_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[5].Count", pyads.PLCTYPE_DWORD, 0, logger_func=srbn_logger, tag_name_for_log="CAM6_B_Good")
                }

                batch_data = {
                    "LastRun_Good": safe_read_by_name(plc, "Packaging.CycleGoodCNT.Count", pyads.PLCTYPE_DINT, 0, logger_func=srbn_logger, tag_name_for_log="Pkg_LR_Good"),
                    "LastRun_Rej1": safe_read_by_name(plc, "Packaging.CycleBad_1CNT.Count", pyads.PLCTYPE_DINT, 0, logger_func=srbn_logger, tag_name_for_log="Pkg_LR_Rej1"),
                    "LastRun_Rej2": safe_read_by_name(plc, "Packaging.CycleBad_2CNT.Count", pyads.PLCTYPE_DINT, 0, logger_func=srbn_logger, tag_name_for_log="Pkg_LR_Rej2"),
                    "Batch_Good": safe_read_by_name(plc, "Packaging.TotalGoodCNT.Count", pyads.PLCTYPE_DINT, 0, logger_func=srbn_logger, tag_name_for_log="Pkg_B_Good"),
                    "Batch_Rej1": safe_read_by_name(plc, "Packaging.TotalBad_1CNT.Count", pyads.PLCTYPE_DINT, 0, logger_func=srbn_logger, tag_name_for_log="Pkg_B_Rej1"),
                    "Batch_Rej2": safe_read_by_name(plc, "Packaging.TotalBad_2CNT.Count", pyads.PLCTYPE_DINT, 0, logger_func=srbn_logger, tag_name_for_log="Pkg_B_Rej2")
                }

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Keep this timestamp format for DB
                # Ensure strings are stripped of null terminators which can come from PLC WSTRINGs
                active_part_cleaned = active_part.rstrip('\x00').strip() if isinstance(active_part, str) else active_part
                operator_name_cleaned = operator_name.rstrip('\x00').strip() if isinstance(operator_name, str) else operator_name
                lot_number_cleaned = lot_number.rstrip('\x00').strip() if isinstance(lot_number, str) else lot_number
                
                log_data = {
                    'timestamp': timestamp, # Standard format for DB
                    'source': 'ADS',
                    'Active_Part': active_part_cleaned,
                    'operator_name': operator_name_cleaned,
                    'Lot_Number': lot_number_cleaned,
                    **cam_data,
                    **batch_data,
                }

                log_to_db(log_data) # This uses its own central logging for info/errors
                _log_worker_message(logger, f"Logged data to DB: {log_data}", level=logging.DEBUG)

            previous_coil_state = coil1_state
            
            if stop_event and stop_event.wait(polling_delay_val):
                _log_worker_message(logger, "Stop event received during polling delay. Exiting loop.", level=logging.INFO)
                break
            elif not stop_event: # Should not happen if stop_event is always provided
                 time.sleep(polling_delay_val)


        except pyads.ADSError as ads_err:
            # This might indicate a more severe issue with PLC communication during the loop
            _log_worker_message(logger, f"ADSError during main logging loop: {ads_err}. Check connection and symbol names.", level=logging.ERROR, exc_info=True)
            # Potentially add retry logic here or attempt to re-open plc connection
            # For now, we break the loop on such an error.
            if plc and plc.is_open:
                try: plc.close()
                except Exception as close_ex: _log_worker_message(logger, f"Exception closing PLC on ADSError: {close_ex}", level=logging.ERROR)
            _log_worker_message(logger, "ADS worker stopping due to ADSError in loop.", level=logging.ERROR)
            break 
        except Exception as e:
            _log_worker_message(logger, f"Unexpected error in ADS logging loop: {e}", level=logging.CRITICAL, exc_info=True)
            # Consider if this should also break or attempt recovery
            if stop_event and stop_event.wait(polling_delay_val * 2): # Longer wait after unexpected error
                break
            elif not stop_event: time.sleep(polling_delay_val * 2)


    _log_worker_message(logger, "Exited main ADS data logging loop.", level=logging.INFO)
    if plc and plc.is_open:
        try:
            plc.close()
            _log_worker_message(logger, "ADS PLC connection closed.", level=logging.INFO)
        except Exception as e:
            _log_worker_message(logger, f"Error closing ADS PLC connection: {e}", level=logging.ERROR, exc_info=True)
    
    _log_worker_message(logger, "ADS data pull worker finished.", level=logging.INFO)
