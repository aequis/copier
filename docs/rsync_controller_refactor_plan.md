# Refactoring Plan: RsyncController

## Problem

The current `src/copier/rsync/controller.py::RsyncController` class has grown complex and handles multiple distinct responsibilities beyond just controlling the rsync process. This includes environment setup, command construction, process management, output processing, state interaction, and application control, violating the Single Responsibility Principle and making the class harder to maintain and test.

## Proposed Solution: Separation into Dedicated Classes

To address this, we will refactor the `RsyncController` by extracting specific responsibilities into new, dedicated classes and renaming the core controller class to better reflect its focused role.

### 1. `RsyncEnvironmentChecker` (New Class)

*   **Location:** `src/copier/rsync/environment.py` (or similar)
*   **Responsibility:**
    *   Check if the `rsync` executable is available in the system's PATH.
    *   Handle platform-specific environment setup, such as adding Git's `usr/bin` directory to the PATH on Windows if `rsync.exe` is found there and not already in the PATH.
*   **Interface:**
    *   Likely an `is_available()` method returning a boolean.
    *   May accept a logger or emit signals/log messages for reporting its actions.
*   **Usage:** Instantiated and used by the `Coordinator` or `RsyncProcessManager` before attempting an rsync operation.

### 2. `RsyncCommandBuilder` (New Class)

*   **Location:** `src/copier/rsync/command.py` (or similar)
*   **Responsibility:**
    *   Take a dictionary of user-selected rsync options (e.g., archive, compress, delete, verbose, progress, dry-run, permissions).
    *   Construct the final list of command-line arguments (`List[str]`) to be passed to the `rsync` executable, handling potential conflicts or implications (e.g., `-a` implies other flags).
*   **Interface:**
    *   A `build_command(options: Dict[str, bool]) -> List[str]` method.
*   **Usage:** Instantiated and used by the `RsyncProcessManager` when preparing to start the `RsyncRunner`.

### 3. `RsyncProcessManager` (Refactored `RsyncController`)

*   **Location:** `src/copier/rsync/manager.py` (Rename `controller.py` or create new)
*   **Responsibility:** Orchestrates the rsync operation lifecycle.
    *   Uses `RsyncCommandBuilder` to get command arguments.
    *   Manages the `RsyncRunner` instance (creation, starting with sources/destination/command, interruption).
    *   Owns and manages the `log_queue` (`queue.Queue`) for receiving messages from `RsyncRunner`.
    *   Owns and manages the `log_timer` (`QTimer`) for processing the queue.
    *   Implements the `process_log_queue` method to handle messages (log, progress, error, finished) from the runner.
    *   Interacts with `AppState` for state management (e.g., reading resume state, updating progress).
    *   Emits signals (`log_signal`, `rsync_finished`, `progress_updated`) for the `Coordinator` to consume.
*   **Dependencies:** `RsyncCommandBuilder`, `RsyncRunner`, `AppState`, `queue`, `PySide6.QtCore`.

### 4. Relocate Application Shutdown Logic

*   The `quit_app` and `_perform_quit` methods will be removed from the rsync-specific class (`RsyncProcessManager`).
*   This logic should reside in a higher-level component responsible for the overall application lifecycle, likely the `Coordinator` (`src/copier/coordinator.py`) or potentially `main.py`.
*   The `Coordinator` will be responsible for requesting the `RsyncProcessManager` to interrupt any running process before initiating the application quit sequence.

## Proposed Structure Diagram

```mermaid
graph TD
    subgraph RsyncEnvironmentChecker
        EC[Check Availability]
        EP[Setup Environment]
    end

    subgraph RsyncCommandBuilder
        CB[Build Command Args]
    end

    subgraph RsyncProcessManager (Focused Role)
        PM_Start[Start/Resume Process]
        PM_Interrupt[Interrupt Process]
        PM_Queue[Process Output Queue]
        PM_State[Interact w/ AppState]
        PM_Log[Emit Logs/Signals]
    end

    subgraph Coordinator (Or Main App)
        Coord_AppCtrl[Application Control (incl. Quit)]
        Coord_Orchestrate[Orchestrate UI & Backend]
    end

    Coordinator -- Uses --> RsyncEnvironmentChecker
    Coordinator -- Uses --> RsyncProcessManager
    RsyncProcessManager -- Uses --> RsyncCommandBuilder
    RsyncProcessManager -- Uses --> RsyncRunner
    RsyncRunner -- Queue --> RsyncProcessManager

    RsyncEnvironmentChecker -- Status/Logs --> Coordinator
    RsyncProcessManager -- Signals/Logs --> Coordinator
    Coordinator -- Manages --> AppState
    Coordinator -- Controls --> QApplication
```

This refactoring promotes better separation of concerns, making the codebase more modular, testable, and easier to understand and maintain.