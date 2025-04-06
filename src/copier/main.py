# src/copier/main.py
import sys

# Import QApplication from the correct Qt binding
try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("Error: Neither PySide6 nor PyQt6 could be imported.")
        print("Please install one of them (e.g., 'pip install PySide6')")
        sys.exit(1)

# Import the AppCoordinator
from copier.coordinator import AppCoordinator

if __name__ == "__main__":
    # 1. Create the QApplication instance (required before any Qt objects)
    # It's important this happens first.
    app = QApplication(sys.argv)

    # 2. Create the AppCoordinator
    # The coordinator will internally create AppState, GuiManager, and RsyncController
    coordinator = AppCoordinator()

    # 3. Run the application via the coordinator
    # The coordinator's run() method shows the GUI and starts the event loop.
    exit_code = coordinator.run()

    # 4. Exit the application
    sys.exit(exit_code)