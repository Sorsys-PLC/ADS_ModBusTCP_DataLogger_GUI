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
                        'coil_1': coils[0],
                        'coil_2': coils[1] if len(coils) > 1 else None,
                        'coil_3': coils[2] if len(coils) > 2 else None,
                        'coil_4': coils[3] if len(coils) > 3 else None,
                        'coil_5': coils[4] if len(coils) > 4 else None,
                        'register_1': registers[0] if len(registers) > 0 else None,
                        'register_2': registers[1] if len(registers) > 1 else None,
                        'register_3': registers[2] if len(registers) > 2 else None,
                        'register_4': registers[3] if len(registers) > 3 else None,
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
