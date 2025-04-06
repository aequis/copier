# Improvement Plan for Copier Application

This plan outlines the steps to enhance the code quality, structure, and features of the Copier application.

**1. Configuration Management**

*   **Goal:** Persist user settings between sessions.
*   **Steps:**
    *   Choose a configuration format (e.g., JSON, INI, or `QSettings`). `QSettings` is often convenient for Qt apps as it handles platform differences.
    *   Identify settings to save:
        *   Rsync option checkbox states (`GuiManager.get_rsync_options`)
        *   Last used destination path (`GuiManager.get_destination`)
        *   Last used source paths (`GuiManager.get_all_sources`) - *Optional, might be less useful.*
        *   Main window size and position.
    *   Implement loading settings on application startup (`RsyncController.__init__` or `main_pyside.py`) and apply them to the GUI.
    *   Implement saving settings on application exit (`RsyncController.quit_app` or using `QApplication.aboutToQuit` signal).
    *   Refactor `config.py`: Use it only to define *default* values for settings if needed, or remove it if defaults are handled directly in `GuiManager` or loaded settings.

**2. Error Handling & Logging**

*   **Goal:** Improve robustness and replace the custom logging queue with Python's standard `logging` module.
*   **Steps:**
    *   **Integrate `logging`:**
        *   Configure the `logging` module in `main_pyside.py` (set level, format).
        *   Add handlers (e.g., `StreamHandler` for console, `FileHandler` for a log file like `copier.log`).
        *   Create a custom `logging.Handler` subclass (`QtLogHandler`) that emits a Qt signal (`Signal(str)`) with formatted log records.
        *   In `RsyncController`, connect this signal to `GuiManager.update_log`. Modify `update_log` to accept the pre-formatted string.
        *   Replace all `self.log_queue.put(('log', ...))` calls in `RsyncRunner` and `RsyncController` with standard `logging.getLogger(...).info(...)`, `error(...)`, etc.
        *   Remove the `log_queue`, `log_timer`, and `process_log_queue` logic from `RsyncController`.
    *   **Enhance Error Handling:**
        *   In `RsyncRunner._execute_single`, analyze non-zero `rsync` return codes more specifically (refer to `rsync` documentation for common codes like permission errors, disk full, etc.) and log more informative error messages.
        *   Add `try...except` blocks around file system operations (e.g., `os.path.exists`) in `RsyncController` where appropriate.

**3. Progress Reporting**

*   **Goal:** Provide clearer progress feedback in the GUI.
*   **Steps:**
    *   **Parse Progress:** In `RsyncRunner._execute_single`, modify the output reading loop to parse lines containing '%' to extract the percentage and potentially the current file being transferred.
    *   **Signal Progress:** Replace `self.log_queue.put(('log', 'progress', line))` with a dedicated signal or logging call, e.g., `logging.getLogger(...).debug(f"Progress: {percent}% - {filename}")` or a new queue message type if sticking with queues temporarily (`('progress_update', percent, filename)`). If using `logging`, the `QtLogHandler` might need modification to handle these specific messages differently or filter them.
    *   **GUI Update:**
        *   Add a `QProgressBar` widget to `GuiManager`.
        *   Create a slot in `GuiManager` (e.g., `update_progress(percent: int, filename: str)`) to update the progress bar and potentially a status label.
        *   Connect the progress signal from the `QtLogHandler` (or queue processor) to this new slot in `RsyncController`.
    *   **Refactor State Update:** The existing `('progress', current_index, total_count)` message used for `StateManager` should be kept separate from the file transfer progress reporting.

**4. Code Structure & Readability**

*   **Goal:** Improve maintainability by reducing controller complexity and clarifying responsibilities.
*   **Steps:**
    *   **Extract Command Builder:** Create a new function or method (e.g., `_build_rsync_command(options: dict, source: str, destination: str) -> List[str]`) within `RsyncController` or a separate utility module to encapsulate the logic from lines `254-297` of `rsync_controller.py`.
    *   **Extract Path Validation:** Create helper functions (e.g., `_validate_source_path(path)`, `_validate_destination_path(path)`) in `RsyncController` or a utility module for the validation logic used in `handle_sources_dropped` and `handle_destination_dropped`.
    *   **Clarify PATH Modification:** Add comments and clearer log messages around the `_add_git_to_path_windows` logic. Consider adding a configuration option to disable this behavior.
    *   **State Synchronization:** Review and ensure `RsyncController`'s internal `source_paths` and `destination_path` are consistently updated *after* GUI changes are confirmed (e.g., within the handler slots like `handle_destination_dropped`).

**5. Testing**

*   **Goal:** Add automated tests to ensure correctness and prevent regressions.
*   **Steps:**
    *   Set up `pytest`. Add `pytest` and potentially `pytest-qt` to `requirements-dev.txt`.
    *   **Unit Tests:**
        *   Create `tests/test_state_manager.py` to test all methods of `StateManager`.
        *   Create `tests/test_rsync_runner.py`. Mock `subprocess.Popen` and the `log_queue` (or `logging`) to test `RsyncRunner` logic (thread start, command building, interruption, queue/log output).
        *   Create `tests/test_rsync_controller.py`. Mock `GuiManager`, `RsyncRunner`, `StateManager`, and `QTimer`/`QApplication` where necessary. Test signal connections, state transitions, command building logic (or call the extracted function), and interaction with `StateManager`.
    *   **Configuration Tests:** Test loading/saving of settings (might require mocking `QSettings` or file I/O).

**6. Dependency Management**

*   **Goal:** Ensure dependencies are correctly listed.
*   **Steps:**
    *   Run `pip freeze > requirements.txt` (or manually update) to ensure `PySide6` and any other direct dependencies are listed.
    *   Update `requirements-dev.txt` to include `pytest`, `pytest-qt` (if used), `mypy`, and any linters (like `flake8` or `ruff`).
    *   Consider adding `mypy.ini` settings for stricter type checking.

**7. GUI Enhancements (Optional - Lower Priority)**

*   **Goal:** Improve user experience.
*   **Steps (Implement as desired):**
    *   Add a `QLineEdit` for custom rsync flags in `GuiManager` and integrate its value during command building in `RsyncController`.
    *   Refine drag-and-drop visual cues (e.g., changing background color on hover).
    *   Implement the `QProgressBar` as described in section 3.