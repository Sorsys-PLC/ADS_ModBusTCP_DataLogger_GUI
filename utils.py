import sqlite3
import logging
import os

# Absolute path to the database
DB_PATH = r"C:\DataLogging\plc_log.db"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Initialize SQLite database based on mode
def initialize_db(mode):
    try:
        print("Database file path:", DB_PATH)  # Debugging: Print the path
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Drop the table if it exists to start fresh (optional)
        cursor.execute("DROP TABLE IF EXISTS plc_data")

        # Create the table based on the mode
        if mode == "ADS":
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS plc_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    Active_Part TEXT,
                    operator_name TEXT, 
                    Lot_Number TEXT,
                    CAM1_LastRun_G INTEGER,   
                    CAM2_LastRun_G INTEGER,
                    CAM3_LastRun_G INTEGER,   
                    CAM4_LastRun_G INTEGER,
                    CAM5_LastRun_G INTEGER,
                    CAM6_LastRun_G INTEGER,
                    CAM1_Batch_G INTEGER,   
                    CAM2_Batch_G INTEGER,
                    CAM3_Batch_G INTEGER,   
                    CAM4_Batch_G INTEGER,
                    CAM5_Batch_G INTEGER,
                    CAM6_Batch_G INTEGER,
                    CAM1_LastRun_NG INTEGER,   
                    CAM2_LastRun_NG INTEGER,
                    CAM3_LastRun_NG INTEGER,   
                    CAM4_LastRun_NG INTEGER,
                    CAM5_LastRun_NG INTEGER,
                    CAM6_LastRun_NG INTEGER,
                    CAM1_Batch_NG INTEGER,   
                    CAM2_Batch_NG INTEGER,
                    CAM3_Batch_NG INTEGER,   
                    CAM4_Batch_NG INTEGER,
                    CAM5_Batch_NG INTEGER,
                    CAM6_Batch_NG INTEGER,
                    LastRun_Good INTEGER,
                    LastRun_Rej1 INTEGER,
                    LastRun_Rej2 INTEGER ,
                    Batch_Good INTEGER,
                    Batch_Rej1 INTEGER,
                    Batch_Rej2 INTEGER,     
                    status TEXT
                )
            ''')
            logging.info("Initialized database for ADS data.")
        elif mode == "TCP":
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS plc_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    Lot_Number INTEGER,
                    CAM_Min REAL,
                    CAM_Max REAL,
                    VALVE_Min REAL,
                    VALVE_Max REAL,
                    Inner_D REAL,
                    Circularity REAL,
                    Oil_Hole TEXT,
                    Result TEXT
                )
            ''')
            logging.info("Initialized database for TCP Modbus data.")
        else:
            logging.error("Invalid mode specified. Use 'ADS' or 'TCP'.")
            return

        conn.commit()
        conn.close()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")


def log_to_db(data):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Prepare query with updated column names
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        values = tuple(data.values())

        cursor.execute(f'''
            INSERT INTO plc_data ({columns})
            VALUES ({placeholders})
        ''', values)

        conn.commit()
        conn.close()
        logging.info(f"Logged data to DB: {data}")
    except Exception as e:
        logging.error(f"Error logging to database: {e}")

