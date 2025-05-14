import time
import logging
from datetime import datetime

from pyModbusTCP.client import ModbusClient
from utils import log_to_db

# Define constants (update with your actual PLC setup)
MODBUS_PLC_IP = "192.168.0.10"
MODBUS_PORT = 502
MODBUS_SLAVE_ID = 1
MODBUS_POLLING_DELAY = 0.5
NUMBER_OF_COILS = 5
NUMBER_OF_32BIT_REGISTERS = 17

def get_uint32_from_registers(registers, index):
    """Safely get a 32-bit unsigned int from two 16-bit registers"""
    if index + 1 < len(registers):
        low = registers[index]
        high = registers[index + 1]
        return (high << 16) | low
    return None

def start_tcp_logging():
    client = ModbusClient(host=MODBUS_PLC_IP, port=MODBUS_PORT, unit_id=MODBUS_SLAVE_ID, auto_open=True, timeout=5)
    previous_coil_state = [0] * NUMBER_OF_COILS  # Track the previous state of all coils

    if not client.open():
        logging.error("Failed to connect to Modbus PLC.")
        return

    while True:
        try:
            # Read the state of all coils
            coils = client.read_coils(0, NUMBER_OF_COILS)
            if not coils:
                logging.warning("Failed to read coils.")
                continue

            # Detect rising edge on coil 1 (index 0)
            if previous_coil_state[0] == 0 and coils[0] == 1:  # Rising edge detected
                logging.info("Rising edge detected on coil 1.")

                # Read the 32-bit registers
                registers = client.read_holding_registers(0, NUMBER_OF_32BIT_REGISTERS * 2)
                if registers:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    log_to_db({
                        'timestamp': timestamp,
                        'source': 'Modbus',
                        'Lot_Number': get_uint32_from_registers(registers, 0),
                        'CAM_Min': get_uint32_from_registers(registers, 2) / 1000.0,
                        'CAM_Max': get_uint32_from_registers(registers, 4) / 1000.0,
                        'VALVE_Min': get_uint32_from_registers(registers, 6) / 1000.0,
                        'VALVE_Max': get_uint32_from_registers(registers, 8) / 1000.0,
                        'Inner_D': get_uint32_from_registers(registers, 10) / 1000.0,
                        'Circularity': get_uint32_from_registers(registers, 12) / 1000.0,
                        'Oil_Hole': "Pass" if len(coils) > 3 and coils[1] else "Fail",
                        'Result': "Pass" if len(coils) > 3 and coils[2] else "Fail"
                    })
                    logging.info(f"Logged data for rising edge on coil 1: Coils={coils}, Registers={registers}")
                else:
                    logging.warning("Failed to read registers.")

            # Update the previous state of the coils
            previous_coil_state = coils

            # Polling delay
            time.sleep(MODBUS_POLLING_DELAY)

        except Exception as e:
            logging.error(f"Error in Modbus logging: {e}")
            break

    client.close()
