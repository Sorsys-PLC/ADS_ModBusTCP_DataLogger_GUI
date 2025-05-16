import sys
import os
sys.path.append(os.path.dirname(__file__))

import customtkinter as ctk
from gui_main import TagEditorApp

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = TagEditorApp()
    app.mainloop()
