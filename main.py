import sys
import os
sys.path.append(os.path.dirname(__file__))

import customtkinter as ctk
from gui_main import TagEditorApp
import logging
import logging.handlers

# --- Centralized Logger Setup ---
LOG_FILENAME = "app.log"
# APP_LOGGER_NAME = "PLCLoggerApp" # We will configure the root logger directly

def setup_central_logger():
    # Configure the root logger
    logger = logging.getLogger() # Get the root logger
    logger.setLevel(logging.DEBUG) # Set the root logger level

    # Prevent multiple handlers if setup_central_logger is called more than once
    if logger.hasHandlers():
        # Clear existing handlers from the root logger to avoid duplication if this function is called again
        # This is important if, for example, tests re-initialize logging.
        for handler in logger.handlers[:]: # Iterate over a copy
            logger.removeHandler(handler)
            handler.close() # Close the handler before removing


    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')

    # Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO) # Console can be less verbose
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler
    # Use TimedRotatingFileHandler to rotate logs, e.g., daily
    fh = logging.handlers.TimedRotatingFileHandler(LOG_FILENAME, when="midnight", backupCount=7)
    fh.setLevel(logging.DEBUG) # File log can be more verbose
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    logger.info("Central logger initialized.")
    return logger

# --- End Centralized Logger Setup ---

if __name__ == "__main__":
    # Initialize logger first
    app_logger = setup_central_logger()
    
    # Pass the logger to the application
    # TagEditorApp and other modules will use logging.getLogger(__name__)
    # which will inherit from the root logger's configuration.
    
    # Get a logger for main.py itself (which will also use the root config)
    main_py_logger = logging.getLogger(__name__)

    main_py_logger.info("Application starting.")
    try:
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        app = TagEditorApp() 
        app.mainloop()
    except Exception as e:
        main_py_logger.critical("Application crashed.", exc_info=True)
        # Optionally, re-raise or handle
    finally:
        main_py_logger.info("Application finished.")
