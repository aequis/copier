# rsync_controller.py
import sys
import os
import queue
import subprocess
from typing import List, Optional, Tuple, Any, Dict

from PySide6 import QtCore
from PySide6.QtCore import QObject, Signal, Slot, QTimer, QRunnable, QThreadPool
from PySide6.QtWidgets import QApplication # For quit

# from copier.gui.manager import GuiManager # Removed
from copier.rsync.runner import RsyncRunner
# Import AppState instead of StateManager
from copier.state_manager import AppState
from copier.config import RSYNC_BASE_COMMAND

class RsyncController(QObject):
    """
    Connects the GuiManager (View) to the RsyncRunner and StateManager (Model/Logic).
    """
    # Signals emitted by the controller
    log_signal = Signal(str, str)           # level, message
    rsync_finished = Signal(bool)           # success: True/False
    progress_updated = Signal(dict)         # Dictionary with progress details
    rsync_availability_checked = Signal(bool) # Emitted after checking rsync

    # Add AppState dependency, keep gui for now
    # Remove gui dependency
    def __init__(self, app_state: AppState, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._app_state = app_state # Store the AppState instance
        # self.gui = gui # No longer needed
        self.runner: Optional[RsyncRunner] = None
        self.log_queue: queue.Queue[Tuple[str, Any]] = queue.Queue()
        # Remove internal state variables - read from AppState instead
        # self.source_paths: List[str] = []
        # self.destination_path: Optional[str] = None
        # self._rsync_available: bool = False

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

        self.log("info", "Controller initialized.")
        self.log("info", f"Using base command options: {' '.join(RSYNC_BASE_COMMAND)}")
        self.check_rsync_availability()
        # Initial state update happens in check_rsync_availability's finally block

    def log(self, level: str, message: str) -> None:
        """Emit a signal to log messages to the GUI."""
        # Ensure logging happens on the main thread if called from elsewhere
        # (though in this design, most logs originate from the controller or queue processor)
        self.log_signal.emit(level, message)

    # Remove _connect_gui_signals method
    def check_rsync_availability(self) -> None:
        """Checks if the rsync command is available."""
        rsync_found = False # Local variable for the check
        try:
            # Add common Git paths on Windows if needed (similar to old main block)
            if sys.platform == "win32":
                self._add_git_to_path_windows()

            cmd: List[str] = ["rsync", "--version"]
            # Use CREATE_NO_WINDOW on Windows to prevent console flash
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=5, creationflags=creationflags)
            self.log("success", "rsync command found.")
            rsync_found = True
        except FileNotFoundError:
            self.log("error", "ERROR: 'rsync' command not found in PATH. Please install rsync.")
        except subprocess.CalledProcessError as e:
            self.log("error", f"Warning: 'rsync --version' failed: {e}")
        except subprocess.TimeoutExpired:
             self.log("warning", "Warning: Checking for rsync timed out.")
        except Exception as e:
            self.log("error", f"An unexpected error occurred while checking for rsync: {e}")
        finally:
            # Emit signal instead of calling _update_gui_state directly
            self.rsync_availability_checked.emit(rsync_found)

    def _add_git_to_path_windows(self) -> None:
        """Adds Git bin directory to PATH on Windows if found and not already present."""
        # Check if rsync is already in PATH to avoid unnecessary searching
        try:
            subprocess.run(["rsync", "--version"], check=True, capture_output=True, timeout=1, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            return # Already found
        except Exception:
            pass # Not found in current PATH, proceed to check common locations

        common_paths: List[str] = [
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Git", "usr", "bin"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Git", "usr", "bin"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Git", "usr", "bin"),
        ]
        path_env: str = os.environ.get("PATH", "")
        for p in common_paths:
            if os.path.exists(os.path.join(p, "rsync.exe")):
                if p not in path_env:
                     self.log("info", f"Adding Git bin path to PATH for this session: {p}")
                     os.environ["PATH"] = p + os.pathsep + path_env
                     # Re-check availability after adding to PATH
                     try:
                         subprocess.run(["rsync", "--version"], check=True, capture_output=True, timeout=1, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                         self.log("info", "rsync found after adding Git path.")
                     except Exception:
                         self.log("warning", "rsync still not found after adding Git path.")
                     break # Found one

    # Remove GUI handler slots - Coordinator handles these by updating AppState
    # @Slot(str)
    # def handle_destination_dropped(self, path: str) -> None: ...
    # @Slot(list)
    # def handle_sources_dropped(self, dropped_paths: List[str]) -> None: ...
    # @Slot(list)
    # def handle_remove_sources(self, items_to_remove: List[str]) -> None: ...

    # Remove _can_run_or_resume method - logic moved to Coordinator/AppState

    # Rename, change signature, remove Slot decorator (called directly by Coordinator)
    def start_rsync(self, sources: List[str], destination: str, options: Dict[str, bool]) -> None:
        """Starts/resumes the background RsyncRunner with provided data."""
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

        # --- Construct final rsync command options ---
        # Get options from AppState
        # Use the 'options' argument passed to the method
        selected_options = options
        final_rsync_command = ["rsync"]

        if selected_options["archive"]:
            final_rsync_command.append("-a") # Archive implies -rlptgoD, including permissions
            # Note: If -a is checked, the "preserve_permissions" checkbox is effectively ignored
            # because -a forces permission preservation. We could disable the perms checkbox
            # when archive is checked in the GUI for clarity, but this logic works.
        else:
            # Build flags individually if archive is off
            final_rsync_command.extend(["-rltD"]) # Base flags: Recursive, links, times, devices/specials
            if selected_options["preserve_permissions"]:
                final_rsync_command.extend(["-pgo"]) # Add permissions, group, owner
            # Add other time flags (these might be redundant with -t in -rltD but explicit doesn't hurt)
            final_rsync_command.extend(["--atimes", "--crtimes", "--omit-dir-times"])

        if selected_options["verbose"]:
            final_rsync_command.append("-v")

        if selected_options["compress"]:
            final_rsync_command.append("-z")

        if selected_options["human"]:
            final_rsync_command.append("-h")

        if selected_options["progress"]:
            final_rsync_command.append("--progress")
        else:
            # Use info=progress2 if --progress is not selected (similar to original base)
            final_rsync_command.append("--info=progress2")

        if selected_options["delete"]:
            final_rsync_command.append("--delete")

        if selected_options["dry_run"]:
            final_rsync_command.append("-n")

        # Remove duplicates just in case (e.g., if -a and -v are added)
        # Note: Order might matter for some flags, but this simple approach should be okay here.
        # A more robust way might be needed if complex flag interactions arise.
        final_rsync_command = list(dict.fromkeys(final_rsync_command)) # Simple deduplication preserving order

        self.log("info", f"Using effective rsync options: {' '.join(final_rsync_command[1:])}") # Log options excluding 'rsync' itself

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

    @Slot()
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

    # Remove the _update_gui_state method entirely, as state changes
    # are now driven by AppState updates triggered by the Coordinator.
    # def _update_gui_state(self) -> None:
    #     ...


    @Slot()
    def quit_app(self) -> None:
        """Handles application exit request."""
        if self.runner and self.runner.is_running():
            self.log("warning", "Exit requested: Attempting to interrupt rsync first...")
            self.request_interrupt()
            # Give interrupt a moment to process before quitting
            QTimer.singleShot(500, self._perform_quit)
        else:
            self._perform_quit()

    def _perform_quit(self) -> None:
        """Actually quits the application."""
        self.log("info", "Exiting application.")
        app_instance = QApplication.instance()
        if app_instance:
            app_instance.quit()

    # Optional: Handle close event if the main window is closed directly
    # def closeEvent(self, event: QtGui.QCloseEvent) -> None:
    #     """Handle the main window's close event."""
    #     self.quit_app()
    #     event.accept() # Or ignore() if quit_app handles everything async