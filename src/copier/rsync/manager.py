# rsync_controller.py
import sys
import os
import queue
import subprocess
from typing import List, Optional, Tuple, Any, Dict
import queue

from PySide6.QtCore import QObject, Signal, Slot, QTimer # QThreadPool, QRunnable not used directly here

# Removed QApplication import as quit logic is moved

# from copier.gui.manager import GuiManager # Removed
from copier.rsync.runner import RsyncRunner
from copier.state_manager import AppState
# from copier.config import RSYNC_BASE_COMMAND # Base command options handled by builder
from .command import RsyncCommandBuilder # Import the new builder

class RsyncProcessManager(QObject):
    """
    Manages the lifecycle of an rsync process via RsyncRunner.

    Uses RsyncCommandBuilder to construct the command and interacts with
    AppState for state management (like resume). It processes output from
    RsyncRunner via a queue and emits signals for logging, progress, and
    completion status.
    """
    # Signals emitted by the controller
    log_signal = Signal(str, str)           # level, message
    rsync_finished = Signal(bool)           # success: True/False
    progress_updated = Signal(dict)         # Dictionary with progress details
    # rsync_availability_checked signal removed (handled by Coordinator/EnvironmentChecker)

    def __init__(self, app_state: AppState, parent: Optional[QObject] = None):
        """
        Initializes the RsyncProcessManager.

        Args:
            app_state: The application state manager.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._app_state = app_state # Store the AppState instance
        # self.gui = gui # No longer needed
        self.runner: Optional[RsyncRunner] = None
        self.log_queue: queue.Queue[Tuple[str, Any]] = queue.Queue()
        # Remove internal state variables - read from AppState instead
        # Internal state variables removed - read from AppState or passed as args

        self._command_builder = RsyncCommandBuilder() # Instantiate the command builder

        # Timer to process the log queue from RsyncRunner
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.process_log_queue)
        self.log_timer.setInterval(100) # Check queue every 100ms

        # Remove GUI signal connections - handled by Coordinator
        # self._connect_gui_signals()
        # Remove direct log connection - handled by Coordinator
        # self.log_signal.connect(self.gui.update_log)
        # Remove direct connection to gui.set_button_states
        # self.update_gui_state_signal.connect(self.gui.set_button_states)

        self.log("info", "RsyncProcessManager initialized.")
        # Base command options logging removed (builder handles options)
        # Rsync availability check removed (handled by Coordinator)

    def log(self, level: str, message: str) -> None:
        """Emit a signal to log messages to the GUI."""
        # Ensure logging happens on the main thread if called from elsewhere
        # (though in this design, most logs originate from the controller or queue processor)
        self.log_signal.emit(level, message)

    # Method check_rsync_availability removed (responsibility moved to RsyncEnvironmentChecker)

    # Method _add_git_to_path_windows removed (responsibility moved to RsyncEnvironmentChecker)

    # GUI handler slots removed (handled by Coordinator)
    # @Slot(str)
    # def handle_destination_dropped(self, path: str) -> None: ...
    # @Slot(list)
    # def handle_sources_dropped(self, dropped_paths: List[str]) -> None: ...
    # @Slot(list)
    # def handle_remove_sources(self, items_to_remove: List[str]) -> None: ...

    # Remove _can_run_or_resume method - logic moved to Coordinator/AppState

    # Rename, change signature, remove Slot decorator (called directly by Coordinator)
    # No Slot decorator needed, called directly by Coordinator
    def start_rsync(self, sources: List[str], destination: str, options: Dict[str, bool]) -> None:
        """
        Starts or resumes the background RsyncRunner.

        Args:
            sources: List of source paths.
            destination: Destination path.
            options: Dictionary of rsync options.
        """
        # Refresh source list from GUI just in case
        # Remove internal state reading and pre-checks - Coordinator does this now.
        # Arguments (sources, destination, options) are passed in.

        # --- Determine start index for resume using AppState ---
        is_resuming = self._app_state.can_resume()
        start_index = self._app_state.get_resume_start_index()

        if is_resuming: # Use the flag determined from AppState
            self.log("info", "-" * 20)
            self.log("info", f"Resuming rsync process from source {start_index + 1}/{len(sources)}...") # Use arg 'sources'
        else:
            # Starting fresh run - reset state manager and clear log
            self._app_state.reset_resume_state() # Reset AppState
            # Remove direct GUI manipulation
            # self.gui.clear_log() # Log clearing should be handled based on state change if needed
            self.log("info", "-" * 20)
            self.log("info", f"Starting rsync process for {len(sources)} source(s)...") # Use arg 'sources'

        # Reset was_interrupted state in StateManager as we are now starting/resuming
        # AppState handles its internal 'was_interrupted' flag via setters/resetters
        # self._app_state.resume_state["was_interrupted"] = False # Don't modify directly

        # --- Construct final rsync command options using the builder ---
        final_rsync_command = self._command_builder.build_command(options)
        self.log("info", f"Using effective rsync options: {' '.join(final_rsync_command[1:])}")

        # Create and start the runner
        self.runner = RsyncRunner(self.log_queue)
        # Pass sources/destination read from AppState
        self.runner.run_all(
            sources=sources,         # Use arg 'sources'
            destination=destination, # Use arg 'destination'
            start_index=start_index,
            base_command=final_rsync_command
        )

        # Coordinator will update state to RUNNING, triggering UI update
        # self._update_gui_state()
        self.log_timer.start() # Start polling the queue

    # No Slot decorator needed, called directly by Coordinator
    def request_interrupt(self) -> None:
        """Requests the RsyncRunner to interrupt the current process."""
        if self.runner and self.runner.is_running():
            self.log("warning", "Sending interrupt request...")
            self.runner.interrupt()
            # Runner will put log messages and eventually 'finished' on queue
            # StateManager.mark_interrupted() will be called in process_log_queue
        else:
            self.log("warning", "No rsync process is currently running to interrupt.")
        # Coordinator will update state to INTERRUPTING, triggering UI update
        # self._update_gui_state()

    # This remains connected to the QTimer's timeout signal
    @Slot()
    def process_log_queue(self) -> None:
        """Processes messages from the RsyncRunner's queue."""
        if not self.runner and not self.log_queue.qsize() > 0 : # Stop timer if runner gone and queue empty
             if self.log_timer.isActive():
                 self.log_timer.stop()
             return

        try:
            while not self.log_queue.empty():
                try:
                    message_tuple: Tuple[str, Any] = self.log_queue.get_nowait()
                    msg_type = message_tuple[0]
                    payload = message_tuple[1:] # Get remaining elements as payload tuple

                    if msg_type == 'log':
                        level, message_text = payload
                        # Don't log raw progress lines directly here, handle via 'progress' type if needed
                        if level != 'progress':
                             self.log(level, message_text)
                    elif msg_type == 'progress':
                        # Example: payload might be (current_index, total_count, item_name, percent_str, speed_str, eta_str)
                        # Adjust based on what RsyncRunner actually puts in the queue
                        progress_data = {
                            "current_item_index": payload[0],
                            "total_items": payload[1],
                            # Add more fields as available from RsyncRunner queue message
                            # "current_item_name": payload[2] if len(payload) > 2 else None,
                            # "overall_percent": payload[3] if len(payload) > 3 else 0,
                            # "current_speed": payload[4] if len(payload) > 4 else "",
                            # "eta": payload[5] if len(payload) > 5 else "",
                        }
                        # Update completion index via AppState
                        self._app_state.update_completion_index(progress_data["current_item_index"], emit_signal=False) # Avoid double signal
                        # Emit progress signal for coordinator
                        self.progress_updated.emit(progress_data)
                    elif msg_type == 'error':
                        error_message, = payload
                        self.log("error", error_message)
                    elif msg_type == 'finished':
                        overall_success, = payload
                        # Determine if interrupted based on runner state *before* clearing it
                        was_interrupted_on_finish = (self.runner is not None and self.runner.interrupted)

                        # Mark interrupted in StateManager if applicable
                        # AppState update will be handled by Coordinator based on rsync_finished signal
                        # if not overall_success and was_interrupted_on_finish:
                        #     self._app_state.mark_interrupted() # Let coordinator handle this

                        final_message: str = ""
                        log_level: str = "info"

                        # Determine final status based on success/interrupt
                        # This logic moves to the coordinator's _handle_rsync_finished slot
                        # Here, just emit the signal
                        self.runner = None # Clear runner instance *before* emitting finished signal? Or after? Let's clear after.

                        # Log the raw outcome
                        if was_interrupted_on_finish:
                             self.log("warning", "Rsync process interrupted by runner.")
                        elif overall_success:
                             self.log("success", "Rsync process finished successfully according to runner.")
                        else:
                             self.log("error", "Rsync process finished with errors according to runner.")

                        # Emit the finished signal for the coordinator to handle state changes
                        self.rsync_finished.emit(overall_success and not was_interrupted_on_finish)
                        self.runner = None # Clear runner instance
                        if self.log_timer.isActive():
                            self.log_timer.stop() # Stop polling
                        # Coordinator handles state update via signal
                        # self._update_gui_state()
                        return # Stop processing this cycle

                except queue.Empty:
                    break # Queue is empty for now, wait for next poll cycle
                except Exception as e:
                    self.log("error", f"Internal error processing log queue: {e}")
                    # Consider stopping polling or handling more gracefully

            # Stop timer if runner is finished and queue is now empty
            if self.runner is None and self.log_queue.empty():
                 if self.log_timer.isActive():
                    self.log_timer.stop()


        except Exception as e:
             self.log("error", f"Error in process_log_queue loop: {e}")
             if self.log_timer.isActive():
                self.log_timer.stop() # Stop timer on unexpected error
             self.runner = None
             # Coordinator handles state update via signal
             # self._update_gui_state()

    # Method _update_gui_state removed (handled by Coordinator/AppState)

    # Method quit_app removed (responsibility moved to Coordinator)

    # Method _perform_quit removed (responsibility moved to Coordinator)

    # Method closeEvent removed (responsibility moved to Coordinator/main)

    # Add helper method for Coordinator to check if running
    def is_running(self) -> bool:
        """Checks if the rsync process (runner) is currently active."""
        return self.runner is not None and self.runner.is_running()