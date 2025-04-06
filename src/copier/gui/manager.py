# gui_manager.py
from __future__ import annotations

import sys
from typing import List, Optional

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Signal, Slot, Qt, QUrl, QMimeData
from PySide6.QtWidgets import (
   QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
   QPushButton, QTextEdit, QScrollArea, QListWidgetItem, QCheckBox,
   QGridLayout # Added QCheckBox, QGridLayout
)
# Import custom widgets
from .widgets import DropLineEdit, DropListWidget

# Widget classes moved to widgets.py


class GuiManager(QWidget):
    """Manages the PySide6 GUI elements and interactions."""

    # Signals emitted for main application logic
    run_resume_clicked = Signal()
    interrupt_clicked = Signal()
    exit_clicked = Signal()
    remove_sources_clicked = Signal(list) # Emits list of selected source strings
    sources_dropped = Signal(list)      # Emits list of dropped source paths
    destination_dropped = Signal(str)   # Emits the dropped destination path
    options_changed = Signal(dict)      # Emits the current options dictionary when any checkbox changes
    # Add AppState dependency
    # Add import for AppStatus and AppState
    from copier.state_manager import AppStatus, AppState

    def __init__(self, app_state: AppState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._app_state = app_state # Store the AppState instance
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

        # --- Rsync Options ---
        options_group = QGroupBox("Rsync Options")
        options_layout = QGridLayout() # Use grid for better alignment
        self.option_archive_checkbox = QCheckBox("Archive (-a)")
        self.option_verbose_checkbox = QCheckBox("Verbose (-v)")
        self.option_compress_checkbox = QCheckBox("Compress (-z)")
        self.option_human_checkbox = QCheckBox("Human-readable (-h)")
        self.option_progress_checkbox = QCheckBox("Show Progress (--progress)")
        self.option_delete_checkbox = QCheckBox("Delete extraneous files (--delete)")
        self.option_dryrun_checkbox = QCheckBox("Dry Run (-n)")
        self.option_perms_checkbox = QCheckBox("Preserve Permissions (-pgo)") # Added

        # Set default states (adjust as needed)
        self.option_archive_checkbox.setChecked(True)
        self.option_verbose_checkbox.setChecked(True)
        self.option_human_checkbox.setChecked(True)
        self.option_progress_checkbox.setChecked(True)
        self.option_compress_checkbox.setChecked(False) # Often good on slow links
        self.option_delete_checkbox.setChecked(False) # Dangerous, default off
        self.option_dryrun_checkbox.setChecked(False)
        self.option_perms_checkbox.setChecked(True) # Default to preserving perms if archive is off

        # Add checkboxes to grid layout
        options_layout.addWidget(self.option_archive_checkbox, 0, 0)
        options_layout.addWidget(self.option_verbose_checkbox, 1, 0)
        options_layout.addWidget(self.option_compress_checkbox, 2, 0)
        options_layout.addWidget(self.option_human_checkbox, 0, 1)
        options_layout.addWidget(self.option_progress_checkbox, 1, 1)
        options_layout.addWidget(self.option_delete_checkbox, 2, 1)
        options_layout.addWidget(self.option_dryrun_checkbox, 0, 2)
        options_layout.addWidget(self.option_perms_checkbox, 1, 2) # Added to grid
        options_layout.setColumnStretch(3, 1) # Add stretch to push cols left
        options_group.setLayout(options_layout)

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
        log_layout.addWidget(self.log_text_edit)
        log_group.setLayout(log_layout)

        # --- Add groups to main layout ---
        main_layout.addWidget(source_group)
        main_layout.addWidget(dest_group)
        main_layout.addWidget(options_group) # Add the new options group
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

        # Connect checkbox state changes to the options changed emitter
        self.option_archive_checkbox.stateChanged.connect(self._emit_options_changed)
        self.option_verbose_checkbox.stateChanged.connect(self._emit_options_changed)
        self.option_compress_checkbox.stateChanged.connect(self._emit_options_changed)
        self.option_human_checkbox.stateChanged.connect(self._emit_options_changed)
        self.option_progress_checkbox.stateChanged.connect(self._emit_options_changed)
        self.option_delete_checkbox.stateChanged.connect(self._emit_options_changed)
        self.option_dryrun_checkbox.stateChanged.connect(self._emit_options_changed)
        self.option_perms_checkbox.stateChanged.connect(self._emit_options_changed)

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

    @Slot()
    def _emit_options_changed(self) -> None:
        """Gathers current options and emits the options_changed signal."""
        current_options = self.get_rsync_options()
        self.options_changed.emit(current_options)

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

    # Removed set_button_states method - functionality moved to update_ui_from_state
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

    def get_rsync_options(self) -> dict[str, bool]:
        """Returns a dictionary of the current rsync option checkbox states."""
        return {
            "archive": self.option_archive_checkbox.isChecked(),
            "verbose": self.option_verbose_checkbox.isChecked(),
            "compress": self.option_compress_checkbox.isChecked(),
            "human_readable": self.option_human_checkbox.isChecked(), # Changed key from "human"
            "progress": self.option_progress_checkbox.isChecked(),
            "delete": self.option_delete_checkbox.isChecked(),
            "dry_run": self.option_dryrun_checkbox.isChecked(),
            "preserve_permissions": self.option_perms_checkbox.isChecked(), # Added
        }

    @Slot()
    def update_ui_from_state(self) -> None:
        """Updates all relevant UI elements based on the current AppState."""
        state = self._app_state # Get the current state

        # --- Update Source List ---
        # Avoid clearing/re-adding if the list hasn't actually changed
        current_gui_sources = self.get_all_sources()
        if current_gui_sources != state.sources:
            self.set_source_list(state.sources) # Use existing method

        # --- Update Destination ---
        if self.destination_line_edit.text() != (state.destination or ""):
            self.destination_line_edit.setText(state.destination or "")

        # --- Update Options Checkboxes ---
        # Note: Key names here should align with AppState._options keys
        self.option_archive_checkbox.setChecked(state.options.get("archive", False))
        self.option_verbose_checkbox.setChecked(state.options.get("verbose", False))
        self.option_compress_checkbox.setChecked(state.options.get("compress", False))
        self.option_human_checkbox.setChecked(state.options.get("human_readable", False))
        self.option_progress_checkbox.setChecked(state.options.get("progress", False))
        self.option_delete_checkbox.setChecked(state.options.get("delete", False))
        # Assuming these keys exist in AppState or default to False if missing
        # TODO: Ensure AppState._options includes 'dry_run' and 'preserve_permissions' or handle missing keys
        self.option_dryrun_checkbox.setChecked(state.options.get("dry_run", False))
        self.option_perms_checkbox.setChecked(state.options.get("preserve_permissions", False))


        # --- Update Control Buttons and Widget Enabled States ---
        status = state.status
        is_running = status in [self.AppStatus.RUNNING, self.AppStatus.INTERRUPTING]
        can_run = state.can_run_or_resume()
        can_resume = state.can_resume()

        # Enable/disable input widgets based on running state
        inputs_enabled = not is_running
        self.source_list_widget.setEnabled(inputs_enabled)
        self.remove_source_button.setEnabled(inputs_enabled)
        self.destination_line_edit.setEnabled(inputs_enabled)
        # Enable/disable options groupbox might be simpler?
        # TODO: Store options_group as self.options_group in _setup_ui if desired
        # Let's disable individual checkboxes for now
        self.option_archive_checkbox.setEnabled(inputs_enabled)
        self.option_verbose_checkbox.setEnabled(inputs_enabled)
        self.option_compress_checkbox.setEnabled(inputs_enabled)
        self.option_human_checkbox.setEnabled(inputs_enabled)
        self.option_progress_checkbox.setEnabled(inputs_enabled)
        self.option_delete_checkbox.setEnabled(inputs_enabled)
        self.option_dryrun_checkbox.setEnabled(inputs_enabled)
        self.option_perms_checkbox.setEnabled(inputs_enabled)


        # Update Run/Resume button
        if is_running:
            self.run_resume_button.setText("Running...")
            self.run_resume_button.setEnabled(False)
        elif can_resume and can_run: # Check both resume possibility and general run conditions
             self.run_resume_button.setText("Resume")
             self.run_resume_button.setEnabled(True)
        else: # Idle or finished state
             self.run_resume_button.setText("Run")
             self.run_resume_button.setEnabled(can_run) # Enable only if basic conditions met

        # Update Interrupt button
        self.interrupt_button.setEnabled(is_running)

        # Update window title with status? Optional.
        # self.setWindowTitle(f"Copier - {status.name}")

        # Note: This replaces the logic previously in set_button_states
        # We might remove set_button_states later.
