import sqlite3
import logging

# Database configuration
DB_PATH = "unified_plc_log.db"

# Initialize SQLite database
def initialize_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create table with separate columns for each coil and register
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plc_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                coil_1 INTEGER,
                coil_2 INTEGER,
                coil_3 INTEGER,
                coil_4 INTEGER,
                coil_5 INTEGER,
                register_1 INTEGER,
                register_2 INTEGER,
                register_3 INTEGER,
                register_4 INTEGER,
                counter INTEGER,
                operator_name TEXT,
                status TEXT
            )
        ''')
        conn.commit()
        conn.close()
        logging.info("Initialized SQLite database with separate fields for coils and registers.")
    except Exception as e:
        logging.error(f"Error initializing SQLite database: {e}")

# Log data to SQLite
def log_to_db(data):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Dynamically construct the SQL query
        columns = [key for key in data if data[key] is not None]
        values = [data[key] for key in columns]

        cursor.execute(f'''
            INSERT INTO plc_data ({', '.join(columns)})
            VALUES ({', '.join(['?'] * len(values))})
        ''', values)

        conn.commit()
        conn.close()
        logging.info(f"Logged data to DB: {data}")
    except Exception as e:
        logging.error(f"Error logging to database: {e}")
