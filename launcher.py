from plyer import notification
import subprocess
import time
import os

# Show a Windows notification
notification.notify(
    title="PLC Data Logging Started",
    message="SORSYS TECHNOLOGIES Inc.",
    timeout=5
)

time.sleep(2)

# Build script path and arguments
script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
logging_mode = "--tcp"
command = ["python", script_path, logging_mode]

# Debug print
print("Running command:", command)

# Run the script
try:
    subprocess.run(command, check=True)
except subprocess.CalledProcessError as e:
    print(f"Error running script: {e}")

