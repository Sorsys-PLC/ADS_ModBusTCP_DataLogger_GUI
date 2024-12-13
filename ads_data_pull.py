def start_ads_data_pull():
    plc = pyads.Connection(ADS_PLC_AMS_ID, ADS_PORT, ADS_PLC_IP)
    previous_coil_state = False  # Track the previous state of coil 1

    while True:
        try:
            plc.open()
            
            # Read the state of coil 1
            coil1_state = plc.read_by_name("MAIN.ADS_Coil1", pyads.PLCTYPE_BOOL)

            # Detect rising edge on coil 1
            if not previous_coil_state and coil1_state:  # Rising edge detected
                logging.info("Rising edge detected on ADS coil 1.")

                # Read additional ADS data
                counter = plc.read_by_name("MAIN.ADS_Counter", pyads.PLCTYPE_DINT)
                operator_name = plc.read_by_name("MAIN.ADS_OperatorName", pyads.PLCTYPE_STRING)
                status = plc.read_by_name("MAIN.ADS_PartSimDetect", pyads.PLCTYPE_BOOL)

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_to_db({
                    'timestamp': timestamp,
                    'source': 'ADS',
                    'counter': counter,
                    'operator_name': operator_name.decode('utf-8') if isinstance(operator_name, bytes) else operator_name,
                    'status': "Active" if status else "Inactive",
                })
                logging.info(f"Logged data for rising edge on ADS coil 1: Counter={counter}, Operator={operator_name}, Status={'Active' if status else 'Inactive'}")

            # Update the previous state of coil 1
            previous_coil_state = coil1_state

            time.sleep(ADS_POLLING_DELAY)

        except Exception as e:
            logging.error(f"Error in ADS data pull: {e}")
        finally:
            plc.close()
