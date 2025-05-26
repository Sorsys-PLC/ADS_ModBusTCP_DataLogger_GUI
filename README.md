# PLC Data Logger and Configurator

<p align="center">
  <img src="GUI-Logger.png" alt="PLC Logger GUI" width="700"/>
  <br/>
  <em>Main window showing logging controls, diagnostics, and tag configuration.</em>
</p>
# PLC Data Logger and Configurator

This application allows users to configure and log data from Programmable Logic Controllers (PLCs) using Modbus TCP and Beckhoff ADS protocols. It provides a graphical interface to manage monitored tags, view diagnostics, and display data charts.

## Features

*   **Dual Protocol Support**: Log data from PLCs via Modbus TCP or Beckhoff ADS protocol.
*   **Tag Configuration**:
    *   Add, edit, and remove tags to be monitored.
    *   Enable/disable individual tags.
    *   Import tags from CSV files (supports Productivity Suite export format).
*   **Real-time Diagnostics**:
    *   Monitor PLC connection status and ping times.
    *   View read success rates.
    *   Display error messages and debug information related to PLC communication.
*   **Data Charting**:
    *   Visualize logged tag data over time using line charts.
    *   Select specific databases and tags for plotting.
    *   Filter data by date and time ranges.
    *   Auto-refresh charts with configurable intervals.
    *   Save charts as images (PNG, PDF, JPG).
*   **Data Export**: Export charted data to CSV files for external analysis.
*   **Configuration Management**:
    *   Save and load global settings (PLC IP, port, polling interval, ADS settings) and tag configurations to a JSON file (`plc_logger_config.json`).
    *   Automatic database naming based on configuration hash and date, ensuring data integrity when configurations change.
*   **Automated Logging**: Can be configured to start logging automatically when PLC connection is healthy.
*   **Task Scheduler Integration**: Includes instructions for setting up the application to run automatically on system startup (Windows Task Scheduler).

## Project Structure

The project is organized as follows:

*   `main.py`: Entry point of the application. Initializes the logger and starts the GUI.
*   `gui_main.py`: Defines the main application window (`TagEditorApp`), manages global settings, and coordinates interactions between different tabs and logging backends.
*   `tcp_logger.py`: Handles Modbus TCP communication, including connecting to the PLC, reading tag data, and logging it to the database. Includes reconnection logic.
*   `ads_data_pull.py`: Handles Beckhoff ADS communication, connecting to the PLC, reading specific predefined data structures, and logging them.
*   `utils.py`: Contains utility functions and classes:
    *   `DBLogger`: Manages SQLite database connections and logging operations.
    *   `load_config`, `calculate_config_hash`, `get_db_path`, `initialize_db`: Handle loading/saving of configurations and dynamic database path generation.
*   `ChartTab.py`: Implements the "Charts" tab in the GUI, responsible for database selection, tag selection, date/time filtering, and rendering plots using Matplotlib.
*   `diagnostics_tab.py`: Implements the "Diagnostics" tab, providing real-time feedback on PLC connection status, ping times, and error messages.
*   `tag_configurator_tab.py`: Implements the "Tag Configurator" tab, allowing users to add, edit, remove, and manage PLC tags.
*   `tag_import_dialog.py`: Provides the GUI dialog for importing tags from CSV files.
*   `tag_import_utils.py`: Contains the logic for parsing CSV files (specifically Productivity Suite exports) to extract tag information.
*   `requirements.txt`: Lists project dependencies.
*   `plc_logger_config.json`: Default configuration file (created/updated by the application).
*   `app.log`: Log file where application events, errors, and debug information are stored.
*   `tests/`: Contains unit tests for various modules.

## Installation

1.  Ensure Python 3.x is installed.
2.  Clone the repository or download the source code.
3.  Navigate to the project directory.
4.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
5.  Run the application:
    ```bash
    python main.py
    ```

## Logging

The application uses a centralized logging system.
*   Logs are saved to `app.log` in the main application directory.
*   The log file rotates daily, and up to 7 backup files are kept.
*   Log entries include timestamp, log level (DEBUG, INFO, WARNING, ERROR, CRITICAL), module name, function name, line number, and the log message.
*   **Information logged includes**:
    *   Application start and stop events.
    *   Configuration loading and saving.
    *   PLC connection attempts, successes, and failures.
    *   Data read operations and errors from `tcp_logger` and `ads_data_pull`.
    *   Database initialization and operations.
    *   GUI actions such as button clicks, tab changes, settings application.
    *   Chart generation and data export processes.
    *   Tag import processes.
    *   Unexpected errors and exceptions with stack traces.

This comprehensive logging is useful for debugging issues and understanding the application's behavior over time.

## Running Tests

Unit tests are provided in the `tests/` directory. To run the tests:

1.  Navigate to the project's root directory.
2.  Run the following command in your terminal:
    ```bash
    python -m unittest discover tests
    ```
    This will automatically discover and run all test cases defined in files matching `test_*.py` within the `tests` directory.

## Autorun with Task Scheduler (Windows)

To configure the application to run automatically on system startup using Windows Task Scheduler:

1.  **Open Task Scheduler**: Press `Win + R`, type `taskschd.msc`, and press Enter.
2.  **Create Basic Task**: In the Task Scheduler, select "Create Basic Task..." from the "Actions" panel on the right.
3.  **Name and Trigger**:
    *   **Name**: Choose a descriptive name, e.g., "PLC Data Logger Startup".
    *   **Trigger**: Select "When I log on" or "When the computer starts" based on your preference.
4.  **Action**: Select "Start a program".
5.  **Configure Program/Script**:
    *   **Program/script**: Browse to your Python executable (e.g., `C:\Path\To\Your\Python\python.exe` or `C:\Path\To\Your\Python\pythonw.exe` for no console window).
    *   **Add arguments (optional)**: Enter the full path to `main.py` (e.g., `"C:\Path\To\Your\Project\main.py"`). Ensure the path is quoted if it contains spaces.
    *   **Start in (optional)**: Enter the full path to your project directory (e.g., `"C:\Path\To\Your\Project\"`). This ensures the application runs with the correct working directory.
6.  **Finish**: Click "Next" and then "Finish".
7.  **Test**: You can test the task by right-clicking on it in the Task Scheduler library and selecting "Run". Restart your computer to verify it runs automatically as configured.

**Note**: Ensure that the paths to `python.exe`/`pythonw.exe` and your script are correct. Using `pythonw.exe` is recommended for GUI applications to avoid showing a console window.
