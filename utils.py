import sqlite3
import logging
import os
import json
import hashlib
from datetime import datetime

CONFIG_FILE = "plc_logger_config.json"
DB_FOLDER = os.path.join(os.environ["USERPROFILE"], "Documents", "PLC_Logs")
os.makedirs(DB_FOLDER, exist_ok=True)

DB_PATH = None
CURRENT_CONFIG_HASH = None

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def calculate_config_hash(config):
    return hashlib.md5(json.dumps(config, sort_keys=True).encode()).hexdigest()

def get_db_path(config_hash):
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}_v_{config_hash[:8]}.db"
    return os.path.join(DB_FOLDER, filename)

def initialize_db():
    global DB_PATH, CURRENT_CONFIG_HASH

    config = load_config()
    tags = config.get("tags", [])
    CURRENT_CONFIG_HASH = calculate_config_hash(config)
    DB_PATH = get_db_path(CURRENT_CONFIG_HASH)

    logging.info(f"Using DB file: {DB_PATH}")

    if os.path.exists(DB_PATH):
        logging.info("Database already exists. Skipping schema creation.")
        return

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
        col_type = "REAL" if tag["type"] == "register" else "TEXT"
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

def log_to_db(data):
    global DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        values = tuple(data.values())
        cursor.execute(f"INSERT INTO plc_data ({columns}) VALUES ({placeholders})", values)
        conn.commit()
        conn.close()
        logging.info("Data logged to DB successfully.")
    except Exception as e:
        logging.error(f"Failed to log data to DB: {e}")
