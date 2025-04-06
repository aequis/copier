# rsync_controller.py
import sys
import os
import queue
import subprocess
from typing import List, Optional, Tuple, Any, Dict

from PySide6 import QtCore
from PySide6.QtCore import QObject, Signal, Slot, QTimer, QRunnable, QThreadPool
from PySide6.QtWidgets import QApplication # For quit

from gui_manager import GuiManager
from rsync_runner import RsyncRunner
from state_manager import StateManager
from config import RSYNC_BASE_COMMAND

class RsyncController(QObject):
    """
    Connects the GuiManager (View) to the RsyncRunner and StateManager (Model/Logic).
    """
    log_signal = Signal(str, str) # level, message
    update_gui_state_signal = Signal(bool, bool) # running, can_resume

    def __init__(self, gui: GuiManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.gui = gui
        self.state_manager = StateManager()
        self.runner: Optional[RsyncRunner] = None
        self.log_queue: queue.Queue[Tuple[str, Any]] = queue.Queue()
        self.source_paths: List[str] = []
        self.destination_path: Optional[str] = None
        self._rsync_available: bool = False # Track rsync availability

        # Timer to process the log queue from RsyncRunner
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.process_log_queue)
        self.log_timer.setInterval(100) # Check queue every 100ms

        self._connect_gui_signals()
        self.log_signal.connect(self.gui.update_log) # Connect internal log signal to GUI
        self.update_gui_state_signal.connect(self.gui.set_button_states) # Connect state signal

        self.log("info", "Controller initialized.")
        self.log("info", f"Using base command options: {' '.join(RSYNC_BASE_COMMAND)}")
        self.check_rsync_availability()
        # Initial state update happens in check_rsync_availability's finally block

    def log(self, level: str, message: str) -> None:
        """Emit a signal to log messages to the GUI."""
        # Ensure logging happens on the main thread if called from elsewhere
        # (though in this design, most logs originate from the controller or queue processor)
        self.log_signal.emit(level, message)

    def _connect_gui_signals(self) -> None:
        """Connect signals from the GuiManager to controller slots."""
        self.gui.run_resume_clicked.connect(self.start_or_resume_rsync)
        self.gui.interrupt_clicked.connect(self.request_interrupt)
        self.gui.exit_clicked.connect(self.quit_app)
        self.gui.remove_sources_clicked.connect(self.handle_remove_sources)
        self.gui.sources_dropped.connect(self.handle_sources_dropped)
        self.gui.destination_dropped.connect(self.handle_destination_dropped)
        # Connect the main window's close event if needed (requires passing main window ref)
        # self.gui.parent().closeEvent = self.closeEvent # Example

    def check_rsync_availability(self) -> None:
        """Checks if the rsync command is available."""
        self._rsync_available = False # Assume not available initially
        try:
            # Add common Git paths on Windows if needed (similar to old main block)
            if sys.platform == "win32":
                self._add_git_to_path_windows()

            cmd: List[str] = ["rsync", "--version"]
            # Use CREATE_NO_WINDOW on Windows to prevent console flash
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=5, creationflags=creationflags)
            self.log("success", "rsync command found.")
            self._rsync_available = True
        except FileNotFoundError:
            self.log("error", "ERROR: 'rsync' command not found in PATH. Please install rsync.")
        except subprocess.CalledProcessError as e:
            self.log("error", f"Warning: 'rsync --version' failed: {e}")
        except subprocess.TimeoutExpired:
             self.log("warning", "Warning: Checking for rsync timed out.")
        except Exception as e:
            self.log("error", f"An unexpected error occurred while checking for rsync: {e}")
        finally:
            self._update_gui_state() # Update buttons based on check result

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

    @Slot(str)
    def handle_destination_dropped(self, path: str) -> None:
        """Handles the destination path being set via drag and drop."""
        is_valid_dest = False
        path = os.path.normpath(path) # Normalize path separators
        if os.path.exists(path):
            if os.path.isdir(path):
                is_valid_dest = True
            else:
                self.log("error", f"Destination must be a directory: {path}")
        else:
            # Allow non-existent destination, rsync can create it
            is_valid_dest = True
            # Check parent dir?
            parent_dir = os.path.dirname(path)
            if parent_dir and not os.path.exists(parent_dir):
                 self.log("warning", f"Destination parent directory does not exist: {parent_dir}")
                 # Allow proceeding, rsync might handle it or fail

        if is_valid_dest:
            self.destination_path = path
            self.gui.set_destination(path) # Update GUI display
            self.log("info", f"Destination set: {path}")
            self._update_gui_state() # Update button states if needed

    @Slot(list)
    def handle_sources_dropped(self, dropped_paths: List[str]) -> None:
        """Handles source files/folders being dropped onto the list."""
        added_count = 0
        list_changed = False
        current_sources_in_gui = set(self.gui.get_all_sources())

        for path in dropped_paths:
            path = os.path.normpath(path) # Normalize path separators
            if not os.path.exists(path):
                self.log("warning", f"Skipped invalid source path: {path}")
                continue
            # Check against internal list AND GUI list to be safe
            if path in self.source_paths or path in current_sources_in_gui:
                # self.log("debug", f"Skipped duplicate source path: {path}") # Optional: less noise
                continue

            self.source_paths.append(path)
            # GUI list is updated by GuiManager itself via its drop handler
            added_count += 1
            list_changed = True

        if added_count > 0:
            self.log("info", f"Added {added_count} source(s).")
            # If list changed, reset resume state
            if list_changed and self.state_manager.was_interrupted:
                self.log("warning", "Source list modified, resume state cleared.")
                self.state_manager.reset_for_new_run()
            self._update_gui_state()

    @Slot(list)
    def handle_remove_sources(self, items_to_remove: List[str]) -> None:
        """Handles the removal of selected sources from the list."""
        removed_count = 0
        list_changed = False
        # items_to_remove contains the text of items removed from the GUI list
        for path in items_to_remove:
            path = os.path.normpath(path) # Normalize path separators
            if path in self.source_paths:
                try:
                    self.source_paths.remove(path)
                    removed_count += 1
                    list_changed = True
                except ValueError:
                     self.log("warning", f"Path '{path}' not found in internal list during removal (concurrent modification?).")

            else:
                # This case should ideally not happen if GUI and internal list are synced
                self.log("warning", f"Path '{path}' removed from GUI but not found in internal list.")
                list_changed = True # Consider it a change anyway

        if removed_count > 0:
            self.log("info", f"Removed {removed_count} source(s).")

        # If list changed, reset resume state
        if list_changed and self.state_manager.was_interrupted:
            self.log("warning", "Source list modified, resume state cleared.")
            self.state_manager.reset_for_new_run()

        self._update_gui_state()


    def _can_run_or_resume(self) -> bool:
        """Check if prerequisites for running or resuming rsync are met."""
        # Need rsync, a destination, and either sources or the ability to resume
        # Refresh source list from GUI before checking
        self.source_paths = self.gui.get_all_sources()
        self.destination_path = self.gui.get_destination()

        can_resume = self.state_manager.can_resume(len(self.source_paths))
        have_sources = bool(self.source_paths)

        return self._rsync_available and bool(self.destination_path) and (have_sources or can_resume)


    @Slot()
    def start_or_resume_rsync(self) -> None:
        """Validates inputs and starts/resumes the background RsyncRunner."""
        # Refresh source list from GUI just in case
        self.source_paths = self.gui.get_all_sources()
        self.destination_path = self.gui.get_destination()

        if not self._can_run_or_resume():
             if not self._rsync_available:
                 self.log("error", "Cannot run: rsync command not found or not working.")
             elif not self.source_paths and not self.state_manager.can_resume(0):
                 self.log("error", "Cannot run: No source files/folders added.")
             elif not self.destination_path:
                 self.log("error", "Cannot run: Destination path must be set.")
             else:
                 self.log("error", "Cannot run: Check sources, destination, and rsync availability.")
             self._update_gui_state() # Ensure buttons reflect inability to run
             return

        # --- Determine start index for resume using StateManager ---
        is_resuming = self.state_manager.can_resume(len(self.source_paths))
        start_index = self.state_manager.get_resume_start_index()

        if is_resuming:
            self.log("info", "-" * 20)
            self.log("info", f"Resuming rsync process from source {start_index + 1}/{len(self.source_paths)}...")
        else:
            # Starting fresh run - reset state manager and clear log
            self.state_manager.reset_for_new_run()
            self.gui.clear_log() # Clear log on fresh run
            self.log("info", "-" * 20)
            self.log("info", f"Starting rsync process for {len(self.source_paths)} source(s)...")

        # Reset was_interrupted state in StateManager as we are now starting/resuming
        self.state_manager.was_interrupted = False # Explicitly reset interrupt flag for the new run

        # Create and start the runner
        self.runner = RsyncRunner(self.log_queue)
        self.runner.run_all(
            sources=self.source_paths,
            destination=self.destination_path, # type: ignore (already checked it's not None)
            start_index=start_index,
            base_command=RSYNC_BASE_COMMAND
        )

        self._update_gui_state() # Update buttons immediately
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
        self._update_gui_state() # May not change immediately, but good practice

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
                        current_index, total_count = payload
                        # Update completion index via StateManager
                        self.state_manager.update_completion_index(current_index)
                        # Optionally update a progress bar or label here
                        # self.log("debug", f"Progress: Item {current_index + 1}/{total_count}")
                    elif msg_type == 'error':
                        error_message, = payload
                        self.log("error", error_message)
                    elif msg_type == 'finished':
                        overall_success, = payload
                        # Determine if interrupted based on runner state *before* clearing it
                        was_interrupted_on_finish = (self.runner is not None and self.runner.interrupted)

                        # Mark interrupted in StateManager if applicable
                        if not overall_success and was_interrupted_on_finish:
                            self.state_manager.mark_interrupted()

                        final_message: str = ""
                        log_level: str = "info"

                        if self.state_manager.was_interrupted: # Check StateManager flag
                            final_message = "Batch processing interrupted."
                            log_level = "warning"
                            # StateManager automatically keeps last_completed_index when marked interrupted
                        elif overall_success:
                            final_message = "Batch processing finished successfully."
                            log_level = "success"
                            self.state_manager.reset_for_new_run() # Reset state on full success
                        else:
                            # If it wasn't an interrupt, it was some other error
                            final_message = "Batch processing finished with one or more errors."
                            log_level = "error"
                            # StateManager automatically keeps last_completed_index if not reset

                        self.log(log_level, final_message)
                        self.runner = None # Clear the runner instance AFTER processing final state
                        if self.log_timer.isActive():
                            self.log_timer.stop() # Stop polling
                        self._update_gui_state() # Update buttons for finished state
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
             self._update_gui_state()


    def _update_gui_state(self) -> None:
        """Updates the GUI button states based on the application state."""
        is_running = self.runner is not None and self.runner.is_running()
        # Check can_resume *after* potential state changes in queue processing
        can_resume = self.state_manager.can_resume(len(self.gui.get_all_sources())) # Use GUI list length
        # Check if basic conditions to run are met
        can_run_now = self._can_run_or_resume()

        # Emit signal to update GUI on the main thread
        self.update_gui_state_signal.emit(is_running, can_resume and can_run_now)


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