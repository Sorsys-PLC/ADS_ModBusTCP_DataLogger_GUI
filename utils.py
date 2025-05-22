import logging
import os
import json
import hashlib
from datetime import datetime
import sqlite3
import threading

CONFIG_FILE = "plc_logger_config.json"
DB_FOLDER = os.path.join(os.environ["USERPROFILE"], "Documents", "PLC_Logs")
os.makedirs(DB_FOLDER, exist_ok=True)

DB_PATH = None
CURRENT_CONFIG_HASH = None

class DBLogger:
    """
    Handles an open SQLite database connection for fast PLC logging.
    Ensures directory exists, uses WAL mode, and is thread-safe.
    """
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None
        self.lock = threading.Lock()

    def open(self):
        """Opens the database connection, ensuring directory exists."""
        if self.conn is None:
            db_dir = os.path.dirname(self.db_file)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            logging.info(f"[DBLogger] Opening DB file: {self.db_file}")
            try:
                self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
                self.conn.execute('PRAGMA journal_mode=WAL;')
            except Exception as e:
                logging.error(f"DB connection error: {e}")
                raise

    def close(self):
        """Closes the database connection if open."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def log(self, table, data):
        """
        Inserts a log entry into the table.
        data: dict {column: value}
        """
        with self.lock:
            columns = ', '.join(data.keys())
            placeholders = ', '.join('?' for _ in data)
            values = tuple(data.values())
            sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
            try:
                self.conn.execute(sql, values)
                self.conn.commit()
            except Exception as e:
                logging.error(f"DB Logging error: {e}")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

def load_config():
    """Loads PLC logger configuration from plc_logger_config.json."""
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def calculate_config_hash(config):
    """Calculates an MD5 hash for the given config dictionary."""
    return hashlib.md5(json.dumps(config, sort_keys=True).encode()).hexdigest()

def get_db_path(config_hash):
    """Generates the database file path using current date and config hash."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}_v_{config_hash[:8]}.db"
    return os.path.join(DB_FOLDER, filename)

def initialize_db():
    """
    Initializes the main logging database, creating the table if needed.
    """
    global DB_PATH, CURRENT_CONFIG_HASH

    config = load_config()
    tags = config.get("tags", [])
    CURRENT_CONFIG_HASH = calculate_config_hash(config)
    DB_PATH = get_db_path(CURRENT_CONFIG_HASH)

    logging.info(f"Using DB file: {DB_PATH}")

    if os.path.exists(DB_PATH):
        logging.info("Database already exists. Skipping schema creation.")
        return

    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Build CREATE TABLE command dynamically
    columns = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "timestamp TEXT NOT NULL",
        "source TEXT NOT NULL"
    ]

    for tag in tags:
        if not tag.get("enabled", True):
            continue
        name = tag["name"].replace(" ", "_")
        col_type = "REAL" if tag["type"].lower() == "register" else "TEXT"
        columns.append(f"{name} {col_type}")

    create_query = f"""
    CREATE TABLE IF NOT EXISTS plc_data (
        {', '.join(columns)}
    )
    """

    cursor.execute(create_query)
    conn.commit()
    conn.close()
    logging.info("Database schema initialized successfully.")
