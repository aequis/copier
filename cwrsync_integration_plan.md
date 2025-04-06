# Plan: Integrating cwRsync as rsync Provider on Windows

**Goal:** Modify the application to use cwRsync (a native Windows port of rsync) instead of relying on potentially unavailable system rsync or the one bundled with Git, while maintaining the existing GUI functionality and command-line option generation.

**Assumptions:**

*   cwRsync provides an `rsync.exe` compatible with the required command-line flags (`--version`, `-a`/`-rltpgoD`, `-v`, `-z`, `-h`, `--progress`/`--info=progress2`, `--delete`, `-n`, `--atimes`, `--crtimes`, `--omit-dir-times`). Minor variations might exist, especially for Windows-specific behaviors (timestamps, permissions).
*   The user will install cwRsync and ensure its `bin` directory (containing `rsync.exe`) is added to the system's PATH environment variable.

**Implementation Steps:**

1.  **Simplify Executable Discovery (`rsync_controller.py`):**
    *   **File:** `rsync_controller.py`
    *   **Functions:** `check_rsync_availability`, `_add_git_to_path_windows`
    *   **Action:** Remove or comment out the logic that specifically searches for `rsync.exe` within Git installation directories (`_add_git_to_path_windows`). The primary check (`check_rsync_availability`) should simply attempt to run `rsync --version` assuming `rsync.exe` (from cwRsync) is findable via the system PATH. Log clear errors if `rsync --version` fails.

2.  **Implement Windows-to-Cygwin Path Conversion (`rsync_runner.py`):**
    *   **File:** `rsync_runner.py`
    *   **Action:** Add the following helper function `_convert_path_to_cygwin(win_path: str) -> str`.
    *   **Details:** This function will reliably convert standard Windows paths (drive letters, UNC, relative) to the `/cygdrive/` or `//server/share` format expected by cwRsync.
    *   **Code:**
        ```python
        import os
        import re

        def _convert_path_to_cygwin(win_path: str) -> str:
            """
            Converts a Windows path to a Cygwin-style path for use with cwRsync.

            Handles:
            - Drive letters (C:\path -> /cygdrive/c/path)
            - Drive roots (C:\ -> /cygdrive/c/, C: -> /cygdrive/c)
            - UNC paths (\\server\share\path -> //server/share/path)
            - Relative paths (subdir\file -> subdir/file)
            - Mixed separators.
            """
            # 1. Normalize first to handle mixed separators, ., .. etc.
            norm_path = os.path.normpath(win_path)

            # 2. Handle UNC paths (\\server\share\...)
            if norm_path.startswith('\\\\'):
                # Convert \\server\share\path to //server/share/path
                return "//" + norm_path[2:].replace('\\', '/')

            # 3. Handle drive letter paths (C:\...)
            # Use regex for robustness, checking for drive letter pattern
            drive_match = re.match(r"([a-zA-Z]):(.*)", norm_path)
            if drive_match:
                drive = drive_match.group(1).lower()
                rest = drive_match.group(2)

                # If 'rest' starts with \ (e.g., C:\path), remove it
                if rest.startswith('\\'):
                    rest = rest[1:]
                # If 'rest' is just '.' (e.g., C: normalized to C:.), treat as drive root
                elif rest == '.':
                     rest = ''

                # Convert remaining backslashes
                rest = rest.replace('\\', '/')

                # Construct the cygdrive path
                # Ensure trailing slash for drive root if original path had it (C:\)
                if not rest and norm_path.endswith('\\'):
                     return f"/cygdrive/{drive}/"
                elif not rest:
                     return f"/cygdrive/{drive}" # For C: case
                else:
                     return f"/cygdrive/{drive}/{rest}"

            # 4. Handle relative paths or paths that don't match above patterns
            # Assume it's a relative path or already POSIX-like; just convert backslashes
            return norm_path.replace('\\', '/')
        ```

3.  **Apply Path Conversion Before Execution (`rsync_runner.py`):**
    *   **File:** `rsync_runner.py`
    *   **Function:** `_build_command` (or within the loop in `run_all` just before calling `_build_command`)
    *   **Action:** Modify the code to call `_convert_path_to_cygwin` on both the `source_path` and `destination` variables before they are appended to the `base_command` list.

4.  **Update User Documentation:**
    *   **Action:** Add instructions to any README or user guide specifying cwRsync as a required dependency on Windows. Include steps for downloading, installing, and adding its `bin` directory to the system PATH.

**Visual Plan:**

```mermaid
graph TD
    A[Start: Use cwRsync on Windows] --> B(Step 1: Simplify rsync Discovery);
    B --> C(Modify rsync_controller.py);
    A --> D(Step 2: Implement Path Conversion);
    D --> E(Add _convert_path_to_cygwin in rsync_runner.py);
    A --> F(Step 3: Apply Path Conversion);
    F --> G(Modify _build_command/run_all in rsync_runner.py);
    A --> H(Step 4: Update Documentation);
    H --> I(Add cwRsync dependency info);
    C & E & G & I --> J(Goal: Application uses cwRsync via PATH with correct paths);
    J --> K(Ready for Implementation);

    subgraph "Code Changes"
        C
        E
        G
    end