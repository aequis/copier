# src/copier/state_manager.py
import sys
import logging
import os
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union

# Import QObject and Signal from the correct Qt binding
try:
    from PySide6.QtCore import QObject, Signal
except ImportError:
    try:
        from PyQt6.QtCore import QObject, pyqtSignal as Signal
    except ImportError:
        print("Error: Neither PySide6 nor PyQt6 could be imported.")
        print("Please install one of them (e.g., 'pip install PySide6')")
        sys.exit(1)


class AppStatus(Enum):
    """Represents the overall status of the application."""
    IDLE = auto()
    CHECKING_RSYNC = auto()
    RSYNC_NOT_FOUND = auto()
    READY = auto()
    RUNNING = auto()
    INTERRUPTING = auto()
    INTERRUPTED = auto()
    FINISHED_SUCCESS = auto()
    FINISHED_ERROR = auto()


class AppState(QObject):
    """
    Manages the centralized state of the Copier application.
    Emits state_changed signal whenever any part of the state is modified.
    """
    state_changed = Signal()
    _logger = logging.getLogger(__name__) # Class level logger

    def __init__(self, parent: Optional[QObject] = None, debug_log_file: str = "copier_state.log") -> None:
        super().__init__(parent)
        self._debug_mode: bool = False
        self._debug_log_file: str = os.path.abspath(debug_log_file) # Store absolute path
        self._configure_logging()

        # Initialize state properties (consider using private attributes)
        self._status: AppStatus = AppStatus.IDLE
        self._rsync_available: bool = False
        self._sources: List[str] = []
        self._destination: Optional[str] = None
        # Default options - Ensure all GUI options have a default boolean value
        self._options: Dict[str, bool] = {
            "archive": True,            # -a
            "compress": True,           # -z
            "progress": True,           # --progress
            "human_readable": True,     # -h
            "delete": False,            # --delete (dangerous, default off)
            "verbose": False,           # -v
            "dry_run": False,           # -n
            "preserve_permissions": True # -pgo (often desired, default on)
            # Note: 'preserve_permissions' might be implicitly handled by 'archive',
            # but having it separate allows finer control if 'archive' is off.
        }
        self._resume_state: Dict[str, Any] = {
            "last_completed_index": -1,
            "was_interrupted": False,
        }
        self._last_error: Optional[str] = None
        self._progress: Dict[str, Any] = {
            "current_item_index": -1,
            "total_items": 0,
            "current_item_name": None,
            "overall_percent": 0, # Example, might need more detail from rsync output
            "current_speed": "", # Example
            "eta": "", # Example
        }

    # --- Getters ---
    # Provide getters to allow read-only access from outside if needed,
    # or components can access _properties directly if passed the instance.

    @property
    def status(self) -> AppStatus:
        return self._status

    @property
    def rsync_available(self) -> bool:
        return self._rsync_available

    @property
    def sources(self) -> List[str]:
        return self._sources

    @property
    def destination(self) -> Optional[str]:
        return self._destination

    @property
    def options(self) -> Dict[str, bool]:
        return self._options

    @property
    def resume_state(self) -> Dict[str, Any]:
        return self._resume_state

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def progress(self) -> Dict[str, Any]:
        return self._progress

    @property
    def debug_mode(self) -> bool:
        """Returns whether debug mode is currently enabled."""
        return self._debug_mode

    # --- Setters (Mutators) ---
    # These methods modify the state and emit the signal

    def set_status(self, status: AppStatus) -> None:
        """Sets the application status and emits state_changed."""
        if self._status != status:
            self._log_state_change("status", self._status, status) # Log before change
            self._status = status
            # Reset error when moving to a non-error state? Maybe.
            if status not in [AppStatus.FINISHED_ERROR, AppStatus.RSYNC_NOT_FOUND]:
                 self.set_last_error(None, emit_signal=False) # Avoid double signal
            self.state_changed.emit()

    def set_rsync_available(self, available: bool, emit_signal: bool = True) -> None:
        """Sets rsync availability and emits state_changed."""
        if self._rsync_available != available:
            self._log_state_change("rsync_available", self._rsync_available, available) # Log before change
            self._rsync_available = available
            if emit_signal:
                self.state_changed.emit()

    def set_sources(self, sources: List[str], emit_signal: bool = True) -> None:
        """Sets the source paths and emits state_changed."""
        # Could add validation here if needed
        new_sources = sorted(list(set(sources))) # Keep unique and sorted
        if self._sources != new_sources:
            self._log_state_change("sources", self._sources, new_sources) # Log before change
            self._sources = new_sources
            # Reset resume state if sources change? Yes.
            self.reset_resume_state(emit_signal=False)
            if emit_signal:
                self.state_changed.emit()

    def set_destination(self, destination: Optional[str], emit_signal: bool = True) -> None:
        """Sets the destination path and emits state_changed."""
        # Could add validation here if needed
        if self._destination != destination:
            self._log_state_change("destination", self._destination, destination) # Log before change
            self._destination = destination
            # Reset resume state if destination changes? Yes.
            self.reset_resume_state(emit_signal=False)
            if emit_signal:
                self.state_changed.emit()

    def set_options(self, options: Dict[str, bool], emit_signal: bool = True) -> None:
        """Sets the rsync options and emits state_changed."""
        if self._options != options:
            self._log_state_change("options", self._options, options) # Log before change
            self._options = options
            # Reset resume state if options change? Yes.
            self.reset_resume_state(emit_signal=False)
            if emit_signal:
                self.state_changed.emit()

    def set_last_error(self, error: Optional[str], emit_signal: bool = True) -> None:
        """Sets the last error message and emits state_changed."""
        if self._last_error != error:
            self._log_state_change("last_error", self._last_error, error) # Log before change
            self._last_error = error
            if emit_signal:
                self.state_changed.emit()

    def update_progress(self, progress_update: Dict[str, Any], emit_signal: bool = True) -> None:
        """Updates progress details and emits state_changed."""
        changed = False
        for key, value in progress_update.items():
            if key in self._progress and self._progress[key] != value:
                self._log_state_change(f"progress.{key}", self._progress[key], value) # Log before change
                self._progress[key] = value
                changed = True
        if changed and emit_signal:
            self.state_changed.emit()

    # --- Resume State Management ---

    def reset_resume_state(self, emit_signal: bool = True) -> None:
        """Resets the resume state for a new run or when inputs change."""
        new_state = {"last_completed_index": -1, "was_interrupted": False}
        if self._resume_state != new_state:
            self._log_state_change("resume_state", self._resume_state, new_state) # Log before change
            self._resume_state = new_state
            if emit_signal:
                self.state_changed.emit()

    def mark_interrupted(self, emit_signal: bool = True) -> None:
        """Marks the current run as interrupted."""
        if not self._resume_state["was_interrupted"]:
            self._log_state_change("resume_state.was_interrupted", False, True) # Log before change
            self._resume_state["was_interrupted"] = True
            if emit_signal:
                self.state_changed.emit()

    def update_completion_index(self, index: int, emit_signal: bool = True) -> None:
        """Updates the index of the last successfully completed item."""
        # Ensure we only move forward.
        if index > self._resume_state["last_completed_index"]:
            self._log_state_change("resume_state.last_completed_index", self._resume_state["last_completed_index"], index) # Log before change
            self._resume_state["last_completed_index"] = index
            if emit_signal:
                self.state_changed.emit()

    # --- Debug Mode ---

    def _configure_logging(self) -> None:
        """Sets up the file handler for debug logging if not already configured."""
        # Avoid adding multiple handlers if re-initialized or called multiple times
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == self._debug_log_file for h in self._logger.handlers):
            log_dir = os.path.dirname(self._debug_log_file)
            if log_dir and not os.path.exists(log_dir):
                try:
                    os.makedirs(log_dir, exist_ok=True)
                except OSError as e:
                    print(f"Warning: Could not create log directory '{log_dir}': {e}", file=sys.stderr)
                    self._debug_log_file = os.path.basename(self._debug_log_file) # Fallback to CWD
                    print(f"Warning: Falling back to log file in current directory: '{self._debug_log_file}'", file=sys.stderr)

            try:
                file_handler = logging.FileHandler(self._debug_log_file, mode='a') # Append mode
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                file_handler.setFormatter(formatter)
                self._logger.addHandler(file_handler)
                self._logger.setLevel(logging.DEBUG) # Ensure logger captures debug messages
                # Prevent propagation to root logger if it has handlers (like basicConfig)
                self._logger.propagate = not logging.root.hasHandlers()
            except Exception as e:
                print(f"Error setting up file logger for '{self._debug_log_file}': {e}", file=sys.stderr)


    def set_debug_mode(self, enabled: bool, emit_signal: bool = True) -> None:
        """Enables or disables debug mode."""
        if self._debug_mode != enabled:
            self._debug_mode = enabled
            print(f"Debug mode {'enabled' if enabled else 'disabled'}. Logging to: {self._debug_log_file if enabled else 'N/A'}")
            self._log_state_change("debug_mode", not enabled, enabled) # Log the change itself
            if emit_signal: # Optionally emit state_changed for UI updates
                 self.state_changed.emit()

    def _log_state_change(self, attribute_name: str, old_value: Any, new_value: Any) -> None:
        """Logs state changes to console and file if debug mode is active."""
        if not self._debug_mode:
            return

        # Format values for better readability, especially enums
        def format_val(val):
            if isinstance(val, Enum):
                return f"{val.__class__.__name__}.{val.name}"
            # Truncate long lists/dicts for console, log full for file
            if isinstance(val, (list, dict)) and len(str(val)) > 100 and attribute_name != "options": # Don't truncate options dict for console
                 return f"{type(val).__name__} (len={len(val)})" # Console friendly
            return repr(val) # Default representation

        # Special handling for dictionary changes (like 'options') to show key diffs
        if isinstance(old_value, dict) and isinstance(new_value, dict):
            all_keys = set(old_value.keys()) | set(new_value.keys())
            changes_logged = False
            for key in sorted(list(all_keys)):
                old_sub_val = old_value.get(key, '<Not Present>')
                new_sub_val = new_value.get(key, '<Not Present>')
                if old_sub_val != new_sub_val:
                    attr_key_name = f"{attribute_name}.{key}"
                    console_msg = f"[DEBUG] State Change: {attr_key_name}: {format_val(old_sub_val)} -> {format_val(new_sub_val)}"
                    log_msg = f"State Change: {attr_key_name}: {repr(old_sub_val)} -> {repr(new_sub_val)}"
                    print(console_msg)
                    if self._logger.hasHandlers():
                        try:
                            self._logger.debug(log_msg)
                        except Exception as e:
                            print(f"Error writing to log file: {e}", file=sys.stderr)
                    else:
                        print(f"Warning: Logger not configured, cannot write log message: {log_msg}", file=sys.stderr)
                    changes_logged = True
            # If no specific key changes were logged (e.g., dicts were identical despite reference change), log the overall change
            if not changes_logged and old_value is not new_value:
                 # Fallback to original logging if no key differences found but objects differ
                 console_msg = f"[DEBUG] State Change: {attribute_name}: {format_val(old_value)} -> {format_val(new_value)}"
                 log_msg = f"State Change: {attribute_name}: {repr(old_value)} -> {repr(new_value)}"
                 print(console_msg)
                 if self._logger.hasHandlers():
                     try:
                         self._logger.debug(log_msg)
                     except Exception as e:
                         print(f"Error writing to log file: {e}", file=sys.stderr)
                 else:
                     print(f"Warning: Logger not configured, cannot write log message: {log_msg}", file=sys.stderr)

        else:
            # Standard logging for non-dictionary attributes or when only one is a dict
            console_msg = f"[DEBUG] State Change: {attribute_name}: {format_val(old_value)} -> {format_val(new_value)}"
            log_msg = f"State Change: {attribute_name}: {repr(old_value)} -> {repr(new_value)}"
            print(console_msg)
            if self._logger.hasHandlers():
                try:
                    self._logger.debug(log_msg)
                except Exception as e:
                    print(f"Error writing to log file: {e}", file=sys.stderr)
            else:
                print(f"Warning: Logger not configured, cannot write log message: {log_msg}", file=sys.stderr)


    # --- Derived State/Helpers ---

    def can_run_or_resume(self) -> bool:
        """Checks if the current state allows starting or resuming rsync."""
        return (
            self._rsync_available and
            bool(self._sources) and
            bool(self._destination) and
            self._status in [AppStatus.READY, AppStatus.FINISHED_SUCCESS, AppStatus.FINISHED_ERROR, AppStatus.INTERRUPTED]
        )

    def can_resume(self) -> bool:
        """
        Checks if a resume operation is possible and meaningful based on current state.
        """
        total_items = len(self._sources)
        return (
            self._resume_state["was_interrupted"] and
            0 <= self._resume_state["last_completed_index"] < (total_items - 1)
        )

    def get_resume_start_index(self) -> int:
        """
        Determines the starting index for a resume operation based on current state.
        """
        if self.can_resume():
             # Start from the item *after* the last completed one.
            return self._resume_state["last_completed_index"] + 1
        return 0 # Start from the beginning otherwise