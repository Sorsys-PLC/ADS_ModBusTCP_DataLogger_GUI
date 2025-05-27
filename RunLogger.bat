@echo off
python C:\Users\admin\Desktop\Python\DataLogger\main.py
@pause

:: Open Task Scheduler (Win + S, search "Task Scheduler").

:: Click Create Task (not Basic Task).

:: On the General tab:

:: Name it something like RunPythonScriptOnBoot.

:: Select Run with highest privileges.

:: Choose Configure for: Windows 10/11.

:: On the Triggers tab:

:: Click New.

:: Begin the task: At startup.

:: On the Actions tab:

:: Click New.

:: Action: Start a program.

:: Program/script: point to your .bat file.

:: On the Conditions and Settings tabs, adjust options as needed (e.g. disable “Start the task only if the computer is on AC power” if on a laptop).

:: Click OK and enter admin credentials if prompted.