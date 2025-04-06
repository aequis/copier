# src/copier/coordinator.py
from typing import Optional, List, Dict

# Import QObject from the correct Qt binding (handle potential PySide6/PyQt6 difference)
try:
    from PySide6.QtCore import QObject, Slot
    from PySide6.QtWidgets import QApplication # Needed for main app lifecycle
except ImportError:
    try:
        from PyQt6.QtCore import QObject, pyqtSlot as Slot
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        # This case should ideally be handled earlier (e.g., in state_manager or main)
        # but added here for robustness during refactoring.
        print("Error: Neither PySide6 nor PyQt6 could be imported.")
        print("Please install one of them (e.g., 'pip install PySide6')")
        import sys
        sys.exit(1)


from copier.state_manager import AppState, AppStatus
from copier.gui.manager import GuiManager
from copier.rsync.controller import RsyncController

class AppCoordinator(QObject):
    """
    Orchestrates the Copier application components.
    Owns the AppState, GuiManager, and RsyncController instances.
    """
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

        # 1. Instantiate the central state
        # Make AppState parentless initially, or parent to coordinator?
        # Let's parent it to the coordinator for lifecycle management.
        self.app_state = AppState(parent=self)

        # 2. Instantiate the GUI Manager
        # GuiManager is a QWidget, typically shown, not parented to QObject coordinator?
        # Let's keep it parentless for now, as it's the main window.
        self.gui_manager = GuiManager(app_state=self.app_state)

        # 3. Instantiate the Rsync Controller
        # Parent controller to coordinator for lifecycle.
        self.rsync_controller = RsyncController(app_state=self.app_state, parent=self)

        # --- Connections ---
        # Connect AppState changes directly to the GUI update slot
        self.app_state.state_changed.connect(self.gui_manager.update_ui_from_state)
        # Connect GUI actions to Coordinator slots
        self.gui_manager.run_resume_clicked.connect(self._handle_run_resume_clicked)
        self.gui_manager.interrupt_clicked.connect(self._handle_interrupt_clicked)
        self.gui_manager.remove_sources_clicked.connect(self._handle_remove_sources_clicked)
        self.gui_manager.sources_dropped.connect(self._handle_sources_dropped)
        self.gui_manager.destination_dropped.connect(self._handle_destination_dropped)
        self.gui_manager.options_changed.connect(self._handle_options_changed)
        self.gui_manager.exit_clicked.connect(self._handle_exit_clicked) # Route exit through coordinator

        # Connect Controller events to Coordinator slots
        self.rsync_controller.log_signal.connect(self._handle_log)
        self.rsync_controller.rsync_finished.connect(self._handle_rsync_finished)
        self.rsync_controller.progress_updated.connect(self._handle_progress_updated)
        self.rsync_controller.rsync_availability_checked.connect(self._handle_rsync_availability_checked)

    def run(self) -> int:
        """Shows the main window and starts the application event loop."""
        self.gui_manager.show()
        # Access the QApplication instance to start the event loop
        app = QApplication.instance()
        if app:
            return app.exec()
        else:
            # This should not happen if main.py sets up QApplication correctly
            print("Error: QApplication instance not found.")
            return 1 # Indicate error

    # --- GUI Action Handlers ---

    @Slot()
    def _handle_run_resume_clicked(self) -> None:
        """Handles the Run/Resume button click by checking state and calling controller."""
        # 1. Check if we can run/resume using AppState
        if not self.app_state.can_run_or_resume():
            # Log appropriate error based on state
            if not self.app_state.rsync_available:
                self._handle_log("error", "Cannot run: rsync command not found or not working.")
            elif not self.app_state.sources and not self.app_state.can_resume():
                self._handle_log("error", "Cannot run: No source files/folders added.")
            elif not self.app_state.destination:
                self._handle_log("error", "Cannot run: Destination path must be set.")
            else:
                 self._handle_log("error", "Cannot run: Check sources, destination, and rsync availability.")
            return # Stop if cannot run

        # 2. Get necessary data from AppState
        sources = self.app_state.sources
        destination = self.app_state.destination
        options = self.app_state.options

        # Ensure destination is not None (should be guaranteed by can_run_or_resume, but check anyway)
        if destination is None:
             self._handle_log("error", "Internal Error: Destination is None despite passing run check.")
             return

        # 3. Update state to RUNNING
        self.app_state.set_status(AppStatus.RUNNING)

        # 4. Call the controller's start_rsync method with the data
        self.rsync_controller.start_rsync(
            sources=sources,
            destination=destination,
            options=options
        )

    @Slot()
    def _handle_interrupt_clicked(self) -> None:
        """Handles the Interrupt button click."""
        # Call controller's interrupt method.
        self.rsync_controller.request_interrupt()
        # Controller currently handles state updates internally/via signals.

    @Slot(list)
    def _handle_remove_sources_clicked(self, sources_to_remove: List[str]) -> None:
        """Handles the removal of sources via the GUI button."""
        # Update AppState first
        current_sources = self.app_state.sources.copy()
        updated_sources = [s for s in current_sources if s not in sources_to_remove]
        if len(updated_sources) != len(current_sources):
            self.app_state.set_sources(updated_sources)
        # Note: The controller's handle_remove_sources also has logic to reset
        # resume state. This logic should eventually live purely in AppState setters.
        # For now, we might call the controller method AFTER updating state,
        # or duplicate the resume reset logic here. Let's update state here.
        # The GUI list itself is updated by GuiManager._emit_remove_sources.

    @Slot(list)
    def _handle_sources_dropped(self, dropped_paths: List[str]) -> None:
        """Handles sources being dropped onto the GUI."""
        # Update AppState
        current_sources = self.app_state.sources.copy()
        # Add only new, valid paths (basic check)
        # TODO: Add more robust path validation later if needed
        new_paths = [p for p in dropped_paths if p not in current_sources] # Basic duplicate check
        if new_paths:
            updated_sources = current_sources + new_paths
            self.app_state.set_sources(updated_sources) # AppState setter handles sorting/uniqueness/resume reset

    @Slot(str)
    def _handle_destination_dropped(self, destination_path: str) -> None:
        """Handles destination being dropped onto the GUI."""
        # Update AppState
        # TODO: Add validation if needed (AppState setter could do this)
        self.app_state.set_destination(destination_path) # AppState setter handles resume reset

    @Slot(dict)
    def _handle_options_changed(self, options: Dict[str, bool]) -> None:
        """Handles changes in the rsync options checkboxes."""
        # Update AppState
        self.app_state.set_options(options) # AppState setter handles resume reset

    @Slot()
    def _handle_exit_clicked(self) -> None:
        """Handles the Exit button click."""
        # For now, delegate to the controller's quit logic which handles interruption.
        # This logic will eventually move here.
        self.rsync_controller.quit_app()

    # --- Rsync Controller Event Handlers ---

    @Slot(str, str)
    def _handle_log(self, level: str, message: str) -> None:
        """Handles log messages emitted by the controller."""
        # For now, pass directly to the GUI manager's log update slot.
        # Later, we might want the coordinator to handle logging differently
        # (e.g., writing to a file as well, filtering, etc.).
        # We also need to update AppState if it's an error message.
        if level.lower() == 'error':
            # Avoid double signal emission if status is already error
            emit_signal = self.app_state.status != AppStatus.FINISHED_ERROR
            self.app_state.set_last_error(message, emit_signal=emit_signal)
            # Optionally set status to error here? Depends on context.
            # self.app_state.set_status(AppStatus.FINISHED_ERROR)

        self.gui_manager.update_log(level, message)

    @Slot(bool)
    def _handle_rsync_finished(self, success: bool) -> None:
        """Handles the completion of the rsync process."""
        # Update AppState based on success/failure/interruption
        # The 'success' boolean from the signal indicates if the runner
        # completed without errors AND wasn't interrupted.
        if success:
            self.app_state.set_status(AppStatus.FINISHED_SUCCESS)
            self.app_state.reset_resume_state() # Clear resume state on full success
        else:
            # If it failed, was it due to interruption or an actual error?
            # We check the resume_state which should have been marked by the controller
            # before emitting the signal (or AppState setter if logic moved).
            # Let's assume AppState reflects interruption status correctly now.
            if self.app_state.resume_state.get("was_interrupted", False):
                 self.app_state.set_status(AppStatus.INTERRUPTED)
                 # Keep resume state as is
            else:
                 self.app_state.set_status(AppStatus.FINISHED_ERROR)
                 # Keep resume state in case user wants to retry/resume failed items

    @Slot(dict)
    def _handle_progress_updated(self, progress_data: Dict[str, any]) -> None:
        """Handles progress updates from the controller."""
        # Update the progress details in AppState
        self.app_state.update_progress(progress_data)
        # AppState will emit state_changed, triggering UI update if needed

    @Slot(bool)
    def _handle_rsync_availability_checked(self, available: bool) -> None:
        """Handles the result of the initial rsync availability check."""
        self.app_state.set_rsync_available(available, emit_signal=False) # Update state
        if available:
            # If rsync is found, move to READY state (assuming not running yet)
            if self.app_state.status == AppStatus.CHECKING_RSYNC or self.app_state.status == AppStatus.IDLE:
                 self.app_state.set_status(AppStatus.READY)
        else:
            # If rsync not found, set status to RSYNC_NOT_FOUND
            self.app_state.set_status(AppStatus.RSYNC_NOT_FOUND)
            self.app_state.set_last_error("rsync command not found in PATH.", emit_signal=False) # Set error message

        # Explicitly emit state_changed now that all related state is updated
        self.app_state.state_changed.emit()


    # --- Utility Methods (if needed) ---