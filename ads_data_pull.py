import pyads
import logging
import time
from datetime import datetime
from utils import log_to_db
from pyads import ADSError  # For safe symbol handling

# Constants for PLC connection
ADS_PLC_AMS_ID = "5.132.118.239.1.1"  # Replace with your AMS ID
ADS_PORT = 851  # ADS port
ADS_PLC_IP = "192.168.0.1"  # PLC IP address
ADS_POLLING_DELAY = 0.5  # Polling delay in seconds

def safe_read_by_name(plc, symbol, plctype, default_value=None):
    """Safely read a symbol from the PLC and handle errors."""
    try:
        value = plc.read_by_name(symbol, plctype)
        return value
    except ADSError as e:
        logging.warning(f"Symbol '{symbol}' not found: {e}")
        return default_value

def start_ads_data_pull():
    logging.info("Starting ADS data pull...")
    plc = pyads.Connection(ADS_PLC_AMS_ID, ADS_PORT, ADS_PLC_IP)
    previous_coil_state = False

    while True:
        try:
            plc.open()

            # Read the state of coil 1 (detect rising edge)
            coil1_state = safe_read_by_name(plc, "MessageToHMI.dataLogTrg", pyads.PLCTYPE_BOOL, False)

            if not previous_coil_state and coil1_state:
                logging.info("Rising edge detected on ADS coil 1.")

                # Read ADS data safely
                active_part = safe_read_by_name(plc, "GV.SelPartName", pyads.PLCTYPE_WSTRING, "N/A")
                lot_number = safe_read_by_name(plc, "GV.ActiveLotNumber", pyads.PLCTYPE_WSTRING, "N/A")
                operator_name = safe_read_by_name(plc, "GV.ActiveOperatorName", pyads.PLCTYPE_WSTRING, "N/A")

                # Read CAM and Batch data safely
                cam_data = {
                    "CAM1_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[0].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM2_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[1].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM3_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[2].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM4_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[3].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM5_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[4].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM6_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[5].Count", pyads.PLCTYPE_DWORD, 0),

                    "CAM1_LastRun_NG": safe_read_by_name(plc, "Inspection.CAM_CycleBadCNT[0].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM2_LastRun_NG": safe_read_by_name(plc, "Inspection.CAM_CycleBadCNT[1].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM3_LastRun_NG": safe_read_by_name(plc, "Inspection.CAM_CycleBadCNT[2].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM4_LastRun_NG": safe_read_by_name(plc, "Inspection.CAM_CycleBadCNT[3].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM5_LastRun_NG": safe_read_by_name(plc, "Inspection.CAM_CycleBadCNT[4].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM6_LastRun_NG": safe_read_by_name(plc, "Inspection.CAM_CycleBadCNT[5].Count", pyads.PLCTYPE_DWORD, 0),

                    "CAM1_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[0].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM2_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[1].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM3_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[2].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM4_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[3].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM5_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[4].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM6_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[5].Count", pyads.PLCTYPE_DWORD, 0),

                    "CAM1_Batch_NG": safe_read_by_name(plc, "Inspection.CAM_TotalBadCNT[0].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM2_Batch_NG": safe_read_by_name(plc, "Inspection.CAM_TotalBadCNT[1].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM3_Batch_NG": safe_read_by_name(plc, "Inspection.CAM_TotalBadCNT[2].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM4_Batch_NG": safe_read_by_name(plc, "Inspection.CAM_TotalBadCNT[3].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM5_Batch_NG": safe_read_by_name(plc, "Inspection.CAM_TotalBadCNT[4].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM6_Batch_NG": safe_read_by_name(plc, "Inspection.CAM_TotalBadCNT[5].Count", pyads.PLCTYPE_DWORD, 0),

                }

                # Read Batch Data
                batch_data = {
                    "LastRun_Good": safe_read_by_name(plc, "Packaging.CycleGoodCNT.Count", pyads.PLCTYPE_DINT, 0),
                    "LastRun_Rej1": safe_read_by_name(plc, "Packaging.CycleBad_1CNT.Count", pyads.PLCTYPE_DINT, 0),
                    "LastRun_Rej2": safe_read_by_name(plc, "Packaging.CycleBad_2CNT.Count", pyads.PLCTYPE_DINT, 0),
                    "Batch_Good": safe_read_by_name(plc, "Packaging.TotalGoodCNT.Count", pyads.PLCTYPE_DINT, 0),
                    "Batch_Rej1": safe_read_by_name(plc, "Packaging.TotalBad_1CNT.Count", pyads.PLCTYPE_DINT, 0),
                    "Batch_Rej2": safe_read_by_name(plc, "Packaging.TotalBad_2CNT.Count", pyads.PLCTYPE_DINT, 0),
                }

                # Prepare and log data
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_data = {
                    'timestamp': timestamp,
                    'source': 'ADS',
                    'Active_Part': active_part.rstrip('\x00').strip(),
                    'operator_name': operator_name.rstrip('\x00').strip(),
                    'Lot_Number': lot_number.rstrip('\x00').strip(),  # Updated column name
                    **cam_data,
                    **batch_data,
                }

                log_to_db(log_data)
                logging.info(f"Logged ADS data: {log_data}")

            previous_coil_state = coil1_state
            time.sleep(ADS_POLLING_DELAY)

        except Exception as e:
            logging.error(f"Error in ADS data pull: {e}")
        finally:
            plc.close()
