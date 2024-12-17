from plyer import notification
import subprocess
import time
import os

# Show a Windows notification
notification.notify(
    title="PLC Data Logging Started",
    message="SORSYS TECHNOLOGIES Inc.",
    timeout=5  # Notification stays for 5 seconds
)

# Wait for the notification to show
time.sleep(2)

# Dynamically get the script path relative to the current folder
script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
logging_mode = "--ads"  # Change to "--tcp" if needed

try:
    subprocess.run(["python", script_path, logging_mode], check=True)
except subprocess.CalledProcessError as e:
    print(f"Error running script: {e}")



