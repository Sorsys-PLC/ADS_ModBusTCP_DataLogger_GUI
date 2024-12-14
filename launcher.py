# pip install win10toast
from win10toast import ToastNotifier
import subprocess
import time

# Show a Windows notification
toaster = ToastNotifier()
toaster.show_toast(
    "Logging Started",
    "Your Python script is now running!",
    duration=5,  # Notification will stay for 5 seconds
    threaded=True
)

# Wait to ensure the notification displays
time.sleep(2)

# Run the main Python script
script_path = r"C:\Scripts\my_script.py"  # Update this to the path of your Python script
subprocess.run(["python", script_path])
