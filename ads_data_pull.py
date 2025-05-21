import pyads
import time
from datetime import datetime
from utils import log_to_db
from pyads import ADSError

ADS_PLC_AMS_ID = "5.132.118.239.1.1"
ADS_PORT = 851
ADS_PLC_IP = "192.168.0.1"
ADS_POLLING_DELAY = 0.5

def safe_read_by_name(plc, symbol, plctype, default_value=None):
    try:
        return plc.read_by_name(symbol, plctype)
    except ADSError:
        return default_value

def start_ads_data_pull(stop_event=None, logger=None):
    config = load_config()
    global_settings = config.get("global_settings", {})
    AMS_NET_ID = global_settings.get("ams_net_id", "5.132.118.239.1.1")
    ADS_PORT = global_settings.get("ams_port", 851)
    ADS_PLC_IP = global_settings.get("ip", "192.168.0.1")
    ADS_POLLING_DELAY = global_settings.get("polling_interval", 0.5)

    plc = pyads.Connection(AMS_NET_ID, ADS_PORT, ADS_PLC_IP)
    previous_coil_state = False

    if logger: logger("Connecting to ADS PLC...")
    try:
        plc.open()
        if logger: logger("Connected to ADS PLC.")
    except Exception as e:
        if logger: logger(f"Failed to connect: {e}")
        return

    while not (stop_event and stop_event.is_set()):
        try:
            coil1_state = safe_read_by_name(plc, "MessageToHMI.dataLogTrg", pyads.PLCTYPE_BOOL, False)

            if not previous_coil_state and coil1_state:
                active_part = safe_read_by_name(plc, "GV.SelPartName", pyads.PLCTYPE_WSTRING, "N/A")
                lot_number = safe_read_by_name(plc, "GV.ActiveLotNumber", pyads.PLCTYPE_WSTRING, "N/A")
                operator_name = safe_read_by_name(plc, "GV.ActiveOperatorName", pyads.PLCTYPE_WSTRING, "N/A")

                cam_data = {
                    "CAM1_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[0].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM2_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[1].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM3_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[2].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM4_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[3].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM5_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[4].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM6_LastRun_G": safe_read_by_name(plc, "Inspection.CAM_CycleGoodCNT[5].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM1_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[0].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM2_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[1].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM3_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[2].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM4_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[3].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM5_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[4].Count", pyads.PLCTYPE_DWORD, 0),
                    "CAM6_Batch_G": safe_read_by_name(plc, "Inspection.CAM_TotalGoodCNT[5].Count", pyads.PLCTYPE_DWORD, 0)
                }

                batch_data = {
                    "LastRun_Good": safe_read_by_name(plc, "Packaging.CycleGoodCNT.Count", pyads.PLCTYPE_DINT, 0),
                    "LastRun_Rej1": safe_read_by_name(plc, "Packaging.CycleBad_1CNT.Count", pyads.PLCTYPE_DINT, 0),
                    "LastRun_Rej2": safe_read_by_name(plc, "Packaging.CycleBad_2CNT.Count", pyads.PLCTYPE_DINT, 0),
                    "Batch_Good": safe_read_by_name(plc, "Packaging.TotalGoodCNT.Count", pyads.PLCTYPE_DINT, 0),
                    "Batch_Rej1": safe_read_by_name(plc, "Packaging.TotalBad_1CNT.Count", pyads.PLCTYPE_DINT, 0),
                    "Batch_Rej2": safe_read_by_name(plc, "Packaging.TotalBad_2CNT.Count", pyads.PLCTYPE_DINT, 0)
                }

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_data = {
                    'timestamp': timestamp,
                    'source': 'ADS',
                    'Active_Part': active_part.rstrip('\x00').strip(),
                    'operator_name': operator_name.rstrip('\x00').strip(),
                    'Lot_Number': lot_number.rstrip('\x00').strip(),
                    **cam_data,
                    **batch_data,
                }

                log_to_db(log_data)
                if logger: logger(f"Logged: {log_data}")

            previous_coil_state = coil1_state
            time.sleep(ADS_POLLING_DELAY)

        except Exception as e:
            if logger: logger(f"ADS Logging error: {e}")
            break

    try:
        plc.close()
        if logger: logger("ADS logging stopped.")
    except:
        pass
