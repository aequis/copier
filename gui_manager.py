# gui_manager.py
from __future__ import annotations

import sys
from typing import List, Optional

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Signal, Slot, Qt, QUrl, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QListWidget, QPushButton, QTextEdit, QScrollArea,
    QListWidgetItem, QAbstractItemView
)

class DropLineEdit(QLineEdit):
    """Custom QLineEdit that accepts file/folder drops."""
    dropped = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        # Make it look read-only but still accept drops
        self.setReadOnly(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(Qt.GlobalColor.lightGray).lighter(120))
        self.setPalette(palette)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            # Check if it's a single directory
            urls = event.mimeData().urls()
            if len(urls) == 1:
                local_path = urls[0].toLocalFile()
                if QtCore.QFileInfo(local_path).isDir():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                local_path = urls[0].toLocalFile()
                if QtCore.QFileInfo(local_path).isDir():
                    self.setText(local_path)
                    self.dropped.emit(local_path)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def setText(self, text: str) -> None:
        """Override setText to ensure read-only appearance is maintained."""
        super().setText(text)
        # Force re-evaluation of read-only state visually if needed
        self.setReadOnly(True)


class DropListWidget(QListWidget):
    """Custom QListWidget that accepts file/folder drops."""
    items_dropped = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) # Allow multi-select

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            dropped_paths = []
            for url in event.mimeData().urls():
                local_path = url.toLocalFile()
                if local_path: # Ensure path is valid
                    # Avoid adding duplicates
                    if not self.findItems(local_path, Qt.MatchFlag.MatchExactly):
                        self.addItem(local_path)
                        dropped_paths.append(local_path)
            if dropped_paths:
                self.items_dropped.emit(dropped_paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class GuiManager(QWidget):
    """Manages the PySide6 GUI elements and interactions."""

    # Signals emitted for main application logic
    run_resume_clicked = Signal()
    interrupt_clicked = Signal()
    exit_clicked = Signal()
    remove_sources_clicked = Signal(list) # Emits list of selected source strings
    sources_dropped = Signal(list)      # Emits list of dropped source paths
    destination_dropped = Signal(str)   # Emits the dropped destination path

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Copier")
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Creates and arranges the UI widgets."""
        main_layout = QVBoxLayout(self)

        # --- Source Selection ---
        source_group = QGroupBox("Sources (Drag & Drop Files/Folders Here)")
        source_layout = QVBoxLayout()
        self.source_list_widget = DropListWidget()
        self.remove_source_button = QPushButton("Remove Selected Source(s)")
        source_layout.addWidget(self.source_list_widget)
        source_layout.addWidget(self.remove_source_button)
        source_group.setLayout(source_layout)

        # --- Destination Selection ---
        dest_group = QGroupBox("Destination (Drag & Drop Folder Here)")
        dest_layout = QVBoxLayout()
        self.destination_line_edit = DropLineEdit()
        dest_layout.addWidget(self.destination_line_edit)
        dest_group.setLayout(dest_layout)

        # --- Controls ---
        control_group = QGroupBox("Controls")
        control_layout = QHBoxLayout()
        self.run_resume_button = QPushButton("Run")
        self.interrupt_button = QPushButton("Interrupt")
        self.interrupt_button.setEnabled(False) # Initially disabled
        self.exit_button = QPushButton("Exit")
        control_layout.addWidget(self.run_resume_button)
        control_layout.addWidget(self.interrupt_button)
        control_layout.addStretch() # Push exit button to the right
        control_layout.addWidget(self.exit_button)
        control_group.setLayout(control_layout)

        # --- Status Log ---
        log_group = QGroupBox("Status Log")
        log_layout = QVBoxLayout()
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        # Optional: Add scroll area if needed, though QTextEdit handles scrolling
        # log_scroll = QScrollArea()
        # log_scroll.setWidgetResizable(True)
        # log_scroll.setWidget(self.log_text_edit)
        log_layout.addWidget(self.log_text_edit)
        log_group.setLayout(log_layout)

        # --- Add groups to main layout ---
        main_layout.addWidget(source_group)
        main_layout.addWidget(dest_group)
        main_layout.addWidget(control_group)
        main_layout.addWidget(log_group)

        self.setLayout(main_layout)

    def _connect_signals(self) -> None:
        """Connects internal widget signals to emission methods."""
        self.run_resume_button.clicked.connect(self._emit_run_resume)
        self.interrupt_button.clicked.connect(self._emit_interrupt)
        self.exit_button.clicked.connect(self._emit_exit)
        self.remove_source_button.clicked.connect(self._emit_remove_sources)

        # Connect custom drop signals to class signals
        self.source_list_widget.items_dropped.connect(self.sources_dropped)
        self.destination_line_edit.dropped.connect(self.destination_dropped)

    # --- Internal Signal Emitters ---
    @Slot()
    def _emit_run_resume(self) -> None:
        self.run_resume_clicked.emit()

    @Slot()
    def _emit_interrupt(self) -> None:
        self.interrupt_clicked.emit()

    @Slot()
    def _emit_exit(self) -> None:
        self.exit_clicked.emit()

    @Slot()
    def _emit_remove_sources(self) -> None:
        selected_items = self.source_list_widget.selectedItems()
        if not selected_items:
            return # Nothing selected

        items_to_remove_text: List[str] = []
        rows_to_remove: List[int] = []

        # Collect items and their rows
        for item in selected_items:
            items_to_remove_text.append(item.text())
            rows_to_remove.append(self.source_list_widget.row(item))

        # Remove items from the widget (iterate backwards by row index)
        for row in sorted(rows_to_remove, reverse=True):
            self.source_list_widget.takeItem(row)

        # Emit signal with the text of removed items
        if items_to_remove_text:
            self.remove_sources_clicked.emit(items_to_remove_text)

    # --- Public Slots / Methods ---
    @Slot(str, str)
    def update_log(self, level: str, message: str) -> None:
        """Appends a formatted message to the status log."""
        color_map = {
            "info": "black",
            "warning": "orange",
            "error": "red",
            "success": "green",
            "progress": "blue",
            "debug": "grey" # Added for completeness
        }
        color = color_map.get(level.lower(), "black")
        formatted_message = f'<font color="{color}">[{level.upper()}] {message}</font>'
        self.log_text_edit.append(formatted_message) # append handles newline

    @Slot(bool, bool)
    def set_button_states(self, running: bool, can_resume_and_runnable: bool) -> None:
        """
        Sets the enabled state and text of control buttons based on runner status
        and whether conditions are met to run/resume.

        Args:
            running: True if the RsyncRunner thread is active.
            can_resume_and_runnable: True if the state allows resuming AND basic run conditions are met.
                                     If running is False, this determines if "Resume" or "Run" is shown/enabled.
        """
        # Basic check if sources and destination are set in the GUI
        has_sources = self.source_list_widget.count() > 0
        has_destination = bool(self.destination_line_edit.text())
        can_start_fresh = has_sources and has_destination

        if running:
            self.run_resume_button.setText("Running...")
            self.run_resume_button.setEnabled(False)
            self.interrupt_button.setEnabled(True)
            self.remove_source_button.setEnabled(False)
            self.source_list_widget.setEnabled(False)
            self.destination_line_edit.setEnabled(False) # Disable editing dest while running
            # Keep destination line edit visually enabled but read-only maybe?
            # self.destination_line_edit.setReadOnly(True) # Already read-only by default design
        elif can_resume_and_runnable: # Not running, but can resume
            self.run_resume_button.setText("Resume")
            self.run_resume_button.setEnabled(True)
            self.interrupt_button.setEnabled(False) # Cannot interrupt when not running
            self.remove_source_button.setEnabled(True) # Allow changes when paused/resumable
            self.source_list_widget.setEnabled(True)
            self.destination_line_edit.setEnabled(True) # Allow changing dest when paused/resumable
        else: # Idle state, cannot resume (or conditions not met for resume)
            self.run_resume_button.setText("Run")
            # Only enable Run if sources and destination are actually set
            self.run_resume_button.setEnabled(can_start_fresh)
            self.interrupt_button.setEnabled(False)
            self.remove_source_button.setEnabled(True)
            self.source_list_widget.setEnabled(True)
            self.destination_line_edit.setEnabled(True)

        # Exit button is always enabled unless specifically handled elsewhere
        # self.exit_button.setEnabled(not running) # Example if needed

    @Slot(list)
    def set_source_list(self, items: list[str]) -> None:
        """Clears and repopulates the source list widget."""
        self.source_list_widget.clear()
        self.source_list_widget.addItems(items)

    def get_selected_sources(self) -> list[str]:
        """Returns the text of the currently selected items in the source list."""
        return [item.text() for item in self.source_list_widget.selectedItems()]

    # Added method to get ALL sources, often needed
    def get_all_sources(self) -> list[str]:
        """Returns the text of all items in the source list."""
        return [self.source_list_widget.item(i).text() for i in range(self.source_list_widget.count())]

    @Slot(str)
    def set_destination(self, path: str) -> None:
        """Sets the text of the destination line edit."""
        self.destination_line_edit.setText(path)

    def get_destination(self) -> str:
        """Returns the text of the destination line edit."""
        return self.destination_line_edit.text()

    @Slot()
    def clear_log(self) -> None:
        """Clears the status log."""
        self.log_text_edit.clear()

# Example usage (for testing purposes, not part of the final app structure)
if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = GuiManager()

    # --- Example Signal Connections (for testing) ---
    def on_run_resume():
        gui.update_log("info", "Run/Resume Clicked!")
        # Simulate running state
        gui.set_button_states(running=True, can_resume=False)
        # Simulate completion after delay
        QtCore.QTimer.singleShot(3000, lambda: gui.set_button_states(running=False, can_resume=False))
        QtCore.QTimer.singleShot(1000, lambda: gui.update_log("progress", "Doing step 1..."))
        QtCore.QTimer.singleShot(2000, lambda: gui.update_log("progress", "Doing step 2..."))
        QtCore.QTimer.singleShot(3000, lambda: gui.update_log("success", "Finished!"))


    def on_interrupt():
        gui.update_log("warning", "Interrupt Clicked!")
        gui.set_button_states(running=False, can_resume=True) # Example: Go to paused state

    def on_exit():
        gui.update_log("info", "Exit Clicked!")
        app.quit()

    def on_remove_sources(sources: list[str]):
        gui.update_log("info", f"Remove Sources Clicked: {sources}")

    def on_sources_dropped(sources: list[str]):
        gui.update_log("info", f"Sources Dropped: {sources}")

    def on_destination_dropped(dest: str):
        gui.update_log("info", f"Destination Dropped: {dest}")
        gui.set_destination(dest) # Update the display as well

    gui.run_resume_clicked.connect(on_run_resume)
    gui.interrupt_clicked.connect(on_interrupt)
    gui.exit_clicked.connect(on_exit)
    gui.remove_sources_clicked.connect(on_remove_sources)
    gui.sources_dropped.connect(on_sources_dropped)
    gui.destination_dropped.connect(on_destination_dropped)

    # --- Example Method Calls (for testing) ---
    gui.set_source_list(["/initial/source1", "/initial/source2"])
    gui.set_destination("/initial/destination")
    gui.update_log("info", "GUI Initialized.")
    gui.update_log("warning", "This is a warning.")
    gui.update_log("error", "This is an error.")

    gui.show()
    sys.exit(app.exec())