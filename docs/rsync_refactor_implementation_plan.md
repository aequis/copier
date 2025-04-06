# Implementation Plan: RsyncController Refactoring

**Goal:** Refactor `RsyncController` into `RsyncProcessManager`, `RsyncEnvironmentChecker`, and `RsyncCommandBuilder` to improve separation of concerns, based on the approved refactoring plan (`docs/rsync_controller_refactor_plan.md`).

**Prerequisites:** Familiarity with the existing codebase (`controller.py`, `coordinator.py`, `runner.py`, `state_manager.py`).

**Steps:**

1.  **File/Directory Setup:**
    *   Create the file `src/copier/rsync/environment.py`.
    *   Create the file `src/copier/rsync/command.py`.
    *   Rename `src/copier/rsync/controller.py` to `src/copier/rsync/manager.py`. *(Note: This will require updating imports in other files later.)*

2.  **Implement `RsyncEnvironmentChecker` (`environment.py`):**
    *   Define the `RsyncEnvironmentChecker` class.
    *   Move the `check_rsync_availability` method logic from the *original* `controller.py` into a method like `check(self) -> bool` or `get_status(self) -> Tuple[bool, str]` (returning availability and a status message/log).
    *   Move the `_add_git_to_path_windows` method logic into this class, making it a private helper method (`_add_git_to_path_windows`).
    *   Adapt the methods to use `self` and potentially accept a logging callback/logger instance in `__init__` or the `check` method for reporting actions.
    *   Add necessary imports (`os`, `sys`, `subprocess`, `typing`).
    *   Add appropriate docstrings.

3.  **Implement `RsyncCommandBuilder` (`command.py`):**
    *   Define the `RsyncCommandBuilder` class.
    *   Create a method `build_command(self, options: Dict[str, bool]) -> List[str]`.
    *   Move the command construction logic (approx. lines 155-200 in the *original* `controller.py`) into this `build_command` method.
    *   Ensure the method correctly processes the `options` dictionary and returns the final command list.
    *   Add necessary imports (`typing`).
    *   Add appropriate docstrings.

4.  **Refactor `RsyncProcessManager` (`manager.py`):**
    *   Rename the class `RsyncController` to `RsyncProcessManager`.
    *   **Remove:** Delete the `check_rsync_availability` and `_add_git_to_path_windows` methods (now in `EnvironmentChecker`).
    *   **Remove:** Delete the command construction logic within `start_rsync` (now in `CommandBuilder`).
    *   **Remove:** Delete the `quit_app` and `_perform_quit` methods (to be moved to `Coordinator`).
    *   **Modify `__init__`:**
        *   Keep `AppState` dependency.
        *   Keep `log_queue`, `log_timer`.
        *   Instantiate `RsyncCommandBuilder` (e.g., `self._command_builder = RsyncCommandBuilder()`).
    *   **Modify `start_rsync`:**
        *   Call `self._command_builder.build_command(options)` to get the `final_rsync_command`.
        *   Keep the rest of the logic (resume state handling, `RsyncRunner` creation/start, `log_timer` start).
    *   **Keep:** `request_interrupt` and `process_log_queue` methods largely as they are (they manage the runner and its output).
    *   **Update Imports:** Add `from .command import RsyncCommandBuilder`. Remove unused imports.
    *   Update docstrings for the class and methods.

5.  **Update `Coordinator` (`coordinator.py`):**
    *   **Update Imports:** Change `from copier.rsync.controller import RsyncController` to `from copier.rsync.manager import RsyncProcessManager` and `from copier.rsync.environment import RsyncEnvironmentChecker`.
    *   **Modify `__init__`:**
        *   Instantiate `self._rsync_checker = RsyncEnvironmentChecker()`.
        *   Instantiate `self._rsync_manager = RsyncProcessManager(self._app_state)`.
        *   Connect signals from `self._rsync_manager` (`log_signal`, `rsync_finished`, `progress_updated`) to appropriate `Coordinator` slots (ensure existing connections are updated/replaced correctly).
    *   **Modify Logic for Starting Rsync:**
        *   Identify the method in `Coordinator` that currently calls the controller's `start_rsync` (e.g., `_handle_start_request`).
        *   Before calling `self._rsync_manager.start_rsync(...)` in that method, call `available, message = self._rsync_checker.get_status()` (adjust based on the actual method signature in `RsyncEnvironmentChecker`).
        *   If `not available`, log the `message` and update `AppState` to reflect the error (e.g., set status to `ERROR` or `IDLE_ERROR`) and prevent `start_rsync` from being called.
    *   **Move Quit Logic:**
        *   Implement `quit_app` and `_perform_quit` methods within the `Coordinator`. Copy the logic from the original `controller.py`.
        *   Ensure `quit_app` checks `self._rsync_manager`'s state (e.g., add an `is_running()` method to `RsyncProcessManager` if needed) and calls `self._rsync_manager.request_interrupt()` if necessary before calling `_perform_quit`.
        *   Connect the appropriate GUI signal (e.g., from `GuiManager.quit_requested`) to the `Coordinator.quit_app` slot.
    *   **Update References:** Replace all uses of the old controller instance/class with the new manager instance/class (`self._rsync_manager`, `RsyncProcessManager`). Search the file for `RsyncController`.
    *   Update docstrings.

6.  **Testing:**
    *   Write unit tests for `RsyncEnvironmentChecker`.
    *   Write unit tests for `RsyncCommandBuilder`.
    *   Update unit tests for `RsyncProcessManager`, mocking `RsyncCommandBuilder` and `RsyncRunner`.
    *   Update unit tests for `Coordinator`, mocking `RsyncEnvironmentChecker` and `RsyncProcessManager`, and testing the environment check and quit logic.

7.  **Manual Testing & Review:**
    *   Run the application.
    *   Test rsync functionality thoroughly (starting, interrupting, resuming, different options, handling rsync not found).
    *   Test application quitting while rsync is idle and running.
    *   Review the code changes for correctness, clarity, and adherence to the plan.