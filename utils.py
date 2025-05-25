import logging
import os
import json
import hashlib
from datetime import datetime
import sqlite3
import threading

# Constants
CONFIG_FILE = "plc_logger_config.json"
"""The default filename for storing application configuration."""

DB_FOLDER = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Documents", "PLC_Logs")
"""The default directory for storing SQLite database log files."""
os.makedirs(DB_FOLDER, exist_ok=True) # Ensure the directory exists on module load

# Module-level globals for database path and config hash
DB_PATH = None
"""Global variable holding the path to the currently active SQLite database file. 
   Set by `initialize_db()`."""
CURRENT_CONFIG_HASH = None
"""Global variable holding the hash of the configuration currently used to determine the DB_PATH.
   Set by `initialize_db()`."""

class DBLogger:
    """
    Manages a thread-safe SQLite database connection for logging PLC data.

    This class handles opening and closing the database connection, creating the
    database directory if it doesn't exist, and provides a method to log data
    entries. It enables WAL (Write-Ahead Logging) mode for better concurrency
    and performance. It can be used as a context manager.

    Attributes:
        db_file (str): The path to the SQLite database file.
        conn (sqlite3.Connection | None): The SQLite connection object. None if not connected.
        lock (threading.Lock): A lock to ensure thread-safe database operations.
    """
    def __init__(self, db_file: str):
        """
        Initializes the DBLogger with the path to the database file.

        Args:
            db_file: The path to the SQLite database file.
        """
        self.db_file = db_file
        self.conn = None
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__) # For internal logging

    def open(self):
        """
        Opens the database connection.

        Ensures the directory for the database file exists and sets the journal
        mode to WAL. If a connection is already open, this method does nothing.
        Raises sqlite3.Error or other exceptions if the connection fails.
        """
        if self.conn is None:
            db_dir = os.path.dirname(self.db_file)
            if db_dir and not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                    self.logger.info(f"Created database directory: {db_dir}")
                except OSError as e:
                    self.logger.error(f"Failed to create database directory {db_dir}: {e}", exc_info=True)
                    # Depending on requirements, could re-raise or handle differently
                    raise # Re-raise as this is critical for DB creation
            
            self.logger.info(f"Opening DB file: {self.db_file}")
            try:
                # check_same_thread=False is used because this DBLogger instance
                # might be shared across threads (main GUI thread, logging worker thread).
                # The internal self.lock handles serializing writes.
                self.conn = sqlite3.connect(self.db_file, check_same_thread=False, timeout=10) # Added timeout
                self.conn.execute('PRAGMA journal_mode=WAL;')
                self.logger.info(f"Database connection opened successfully to {self.db_file} in WAL mode.")
            except sqlite3.Error as e: # More specific exception
                self.logger.error(f"SQLite DB connection error for {self.db_file}: {e}", exc_info=True)
                self.conn = None # Ensure conn is None if open failed
                raise # Re-raise the exception to signal failure to the caller
            except Exception as e: # Catch any other unexpected error
                self.logger.error(f"Unexpected error opening DB {self.db_file}: {e}", exc_info=True)
                self.conn = None
                raise


    def close(self):
        """Closes the database connection if it is currently open."""
        if self.conn:
            self.logger.info(f"Closing DB connection to {self.db_file}.")
            try:
                self.conn.close()
            except Exception as e:
                self.logger.error(f"Error closing DB connection to {self.db_file}: {e}", exc_info=True)
            finally:
                self.conn = None

    def log(self, table: str, data: dict):
        """
        Inserts a log entry (a dictionary of data) into the specified table.

        This operation is thread-safe due to an internal lock.

        Args:
            table: The name of the table to insert data into.
            data: A dictionary where keys are column names and values are the
                  corresponding values to insert.
        """
        if self.conn is None:
            self.logger.error(f"Attempted to log to table '{table}' but database connection is not open.")
            # Consider whether to attempt re-opening or raise an error.
            # For robustness in a logging scenario, might try to reopen.
            # However, if it's closed, there's usually a reason.
            # Raising an error or specific exception might be better.
            # For now, just log and return.
            return

        with self.lock:
            try:
                columns = ', '.join(f'"{k}"' for k in data.keys()) # Quote column names
                placeholders = ', '.join('?' for _ in data)
                values = tuple(data.values())
                sql = f"INSERT INTO \"{table}\" ({columns}) VALUES ({placeholders})"
                
                self.conn.execute(sql, values)
                self.conn.commit()
                self.logger.debug(f"Logged data to table '{table}': {data}")
            except sqlite3.Error as e: # More specific
                self.logger.error(f"DB Logging error to table '{table}': {e}. SQL: {sql}, Data: {values}", exc_info=True)
            except Exception as e: # Catch any other unexpected error
                self.logger.error(f"Unexpected error logging to table '{table}': {e}", exc_info=True)


    def __enter__(self):
        """Context manager entry: opens the database connection."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit: closes the database connection."""
        self.close()

def load_config() -> dict:
    """
    Loads the application configuration from `plc_logger_config.json`.

    If the file is not found, is malformed, or another error occurs,
    it logs the issue and returns a default configuration.

    Returns:
        A dictionary containing the loaded configuration or default values.
    """
    logger = logging.getLogger(__name__)
    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)
            logger.info(f"Configuration loaded successfully from {CONFIG_FILE}.")
            return config_data
    except FileNotFoundError:
        logger.warning(f"{CONFIG_FILE} not found. Returning default configuration.")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding {CONFIG_FILE}: {e}. Returning default configuration.", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error loading {CONFIG_FILE}: {e}. Returning default configuration.", exc_info=True)
    
    # Return default configuration if any error occurs
    # This default structure should be consistent with what the application expects.
    return {
        "global_settings": {
            "mode": "TCP", "ip": "192.168.0.10", "port": 502, 
            "polling_interval": 0.5, "ams_net_id": "", "ams_port": 851
        },
        "tags": []
    }

def calculate_config_hash(config: dict) -> str:
    """
    Calculates an MD5 hash (first 8 characters) for the given configuration dictionary.

    The configuration is dumped to a JSON string with sorted keys to ensure
    that semantically identical configurations produce the same hash.

    Args:
        config: The configuration dictionary.

    Returns:
        An 8-character hexadecimal string representing the MD5 hash.
    """
    config_string = json.dumps(config, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.md5(config_string).hexdigest()[:8] # Return first 8 chars for brevity

def get_db_path(config_hash: str) -> str:
    """
    Generates a database file path based on the current date and a configuration hash.

    The filename format is `YYYY-MM-DD_v_<config_hash_prefix>.db`.
    Ensures the `DB_FOLDER` directory exists.

    Args:
        config_hash: The hash of the configuration (typically 8 characters).

    Returns:
        The absolute path for the database file.
    """
    logger = logging.getLogger(__name__)
    # Ensure DB_FOLDER exists (it's also created at module load, but good to double check)
    try:
        os.makedirs(DB_FOLDER, exist_ok=True)
    except OSError as e:
        logger.error(f"Error ensuring DB_FOLDER ({DB_FOLDER}) exists: {e}", exc_info=True)
        # Fallback or re-raise, depending on how critical this is.
        # For now, let it proceed, os.path.join will still form a path.

    date_str = datetime.now().strftime("%Y-%m-%d")
    # Using full hash in filename might be too long for some systems/users,
    # but first 8 chars from calculate_config_hash is generally fine.
    filename = f"plc_data_{date_str}_config-{config_hash}.db" 
    return os.path.join(DB_FOLDER, filename)

def initialize_db():
    """
    Initializes the main logging database based on the current configuration.

    This function performs several key steps:
    1. Loads the application configuration using `load_config()`.
    2. Calculates a hash of the loaded configuration using `calculate_config_hash()`.
    3. Determines the database path using `get_db_path()` with the config hash.
       This sets the global `DB_PATH` and `CURRENT_CONFIG_HASH`.
    4. If the database file does not exist at the determined path, it creates the
       database and a table named `plc_data`.
    5. The `plc_data` table schema is dynamically built based on the 'tags'
       defined in the configuration. It includes standard columns (id, timestamp, source)
       and a column for each enabled tag.

    This ensures that different configurations or significant changes to tags will
    result in data being logged to a new database file, preserving historical data
    integrity.
    """
    logger = logging.getLogger(__name__)
    global DB_PATH, CURRENT_CONFIG_HASH

    config = load_config() # load_config now handles its own logging for errors
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
