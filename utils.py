import sqlite3
import logging
import os
from datetime import datetime



logging.basicConfig(
    level=logging.INFO,  # <-- this hides DEBUG logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)

level=logging.INFO
# Absolute path to the database
##DB_PATH = r"C:\DataLogging\plc_log.db"
##os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Set up logging level (optional, you can also do this in your main script)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Folder where daily log databases will be stored
BASE_DB_FOLDER = os.path.join(os.environ["USERPROFILE"], "Documents", "PLC_Logs")
os.makedirs(BASE_DB_FOLDER, exist_ok=True)

DB_PATH = None
current_log_date = None
current_mode = None

def get_db_path(mode):
    date_str = datetime.now().strftime("%Y-%m-%d")
    suffix = "tcp_log" if mode == "TCP" else "ads_log"
    filename = f"{date_str}_{suffix}.db"
    full_path = os.path.join(BASE_DB_FOLDER, filename)
    logging.debug(f"Constructed DB path: {full_path}")
    return full_path


# Initialize SQLite database based on mode
def initialize_db(mode):    
    global DB_PATH
    DB_PATH = get_db_path(mode)

    logging.info(f"Initializing database for mode: {mode}")
    logging.debug(f"Database full path: {DB_PATH}")

    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        logging.debug(f"Ensured directory exists: {os.path.dirname(DB_PATH)}")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        logging.debug("Opened SQLite connection")

        #cursor.execute("DROP TABLE IF EXISTS plc_data")
        logging.debug("Dropped existing plc_data table (if any)")

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
        raise

def log_to_db(data):
    global DB_PATH, current_log_date, current_mode
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if current_log_date != today_str or not os.path.exists(DB_PATH):
        logging.info("Date changed or DB file missing — rotating log file.")
        initialize_db(current_mode)
        
    if not DB_PATH:
        logging.error("Database path is not set. Did you call initialize_db(mode)?")
        return

    try:
        logging.debug(f"Logging data to DB: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        values = tuple(data.values())

        logging.debug(f"SQL: INSERT INTO plc_data ({columns}) VALUES ({placeholders})")
        logging.debug(f"Values: {values}")

        cursor.execute(f'''
            INSERT INTO plc_data ({columns})
            VALUES ({placeholders})
        ''', values)

        conn.commit()
        conn.close()
        logging.info("Data successfully logged.")

    except Exception as e:
        logging.error(f"Error logging to database: {e}")