# DataLogger

Open Task Scheduler:

Press Win + R, type taskschd.msc, and press Enter.
Create a New Task:

In the Task Scheduler, select Create Basic Task on the right-hand panel.
Follow the wizard:
Name: PLC Data Logger Startup
Trigger: Select When the computer starts or When I log on.
Action: Select Start a program.
Configure the Program:

For Program/script, browse and select your Python executable:
shell
Copy code
C:\Path\To\Python\python.exe
In Add arguments, type the path to your script:
shell
Copy code
"C:\Path\To\Your\launcher.py"
Click Next → Finish.
Test the Task:

Right-click on the task in Task Scheduler and select Run.
Restart your computer to verify it runs automatically.