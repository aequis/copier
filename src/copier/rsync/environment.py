# src/copier/rsync/environment.py
"""
Handles checking the rsync environment, particularly rsync availability.
"""

import os
import subprocess
import sys
import typing

# Placeholder for potential logging callback or logger type
LoggerCallback = typing.Callable[[str], None]


class RsyncEnvironmentChecker:
    """
    Checks for the availability of the rsync executable and handles
    platform-specific environment adjustments (e.g., PATH on Windows).
    """

    def __init__(self, logger: typing.Optional[LoggerCallback] = None):
        """
        Initializes the checker.

        Args:
            logger: An optional callable for logging messages.
        """
        self._log = logger or (lambda msg: print(f"RsyncEnvironmentChecker: {msg}"))

    def _add_git_to_path_windows(self) -> None:
        """
        Adds Git's usr/bin directory to the PATH on Windows if rsync.exe
        is found there and not already in the PATH. This is a common location
        for rsync when Git for Windows is installed.
        """
        if sys.platform != "win32":
            return

        git_path = os.environ.get("ProgramFiles", "C:\\Program Files") + "\\Git\\usr\\bin"
        if os.path.exists(os.path.join(git_path, "rsync.exe")):
            current_path = os.environ.get("PATH", "")
            if git_path not in current_path.split(os.pathsep):
                self._log(f"Adding Git bin directory to PATH: {git_path}")
                os.environ["PATH"] = f"{current_path}{os.pathsep}{git_path}"
            else:
                self._log("Git bin directory already in PATH.")
        else:
            self._log("rsync.exe not found in standard Git bin directory.")


    def get_status(self) -> typing.Tuple[bool, str]:
        """
        Checks if the rsync executable is available in the system's PATH.

        On Windows, it attempts to add Git's bin directory to the PATH if
        rsync is found there.

        Returns:
            A tuple containing:
                - bool: True if rsync is found, False otherwise.
                - str: A status message indicating the result or actions taken.
        """
        if sys.platform == "win32":
            self._add_git_to_path_windows()

        try:
            # Use subprocess.run to check for the executable
            # Capture output to prevent it from printing to console
            # Check=True will raise CalledProcessError if the command fails (e.g., not found)
            # Adding '--version' is a common way to check if an executable runs
            subprocess.run(["rsync", "--version"], check=True, capture_output=True, text=True)
            self._log("rsync found in PATH.")
            return True, "rsync found in PATH."
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            error_message = f"rsync not found in PATH or failed to execute: {e}"
            self._log(error_message)
            return False, error_message

# Example usage (for testing purposes)
if __name__ == "__main__":
    checker = RsyncEnvironmentChecker()
    available, message = checker.get_status()
    print(f"Rsync Available: {available}")
    print(f"Status Message: {message}")
    # Verify PATH modification on Windows if applicable
    if sys.platform == "win32":
        print(f"Current PATH includes Git?: {'Git\\usr\\bin' in os.environ.get('PATH', '')}")