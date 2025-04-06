# main_pyside.py
import sys
from PySide6.QtWidgets import QApplication
from copier.gui.manager import GuiManager
from copier.rsync.controller import RsyncController

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Create the GUI Manager (View)
    gui = GuiManager()

    # Create the Controller and link it to the GUI
    controller = RsyncController(gui=gui)

    # Optional: Connect main window close event to controller's quit handler
    # This ensures the interrupt logic runs if the user closes the window
    # Note: For this to work directly, GuiManager would need to inherit from QMainWindow
    # or be embedded in one. A simpler approach is relying on the Exit button.
    # If GuiManager is the top-level window, this might work:
    # gui.closeEvent = controller.quit_app # Connect close event to quit logic

    # Show the GUI
    gui.show()

    # Start the application event loop
    sys.exit(app.exec())