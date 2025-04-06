import subprocess
import threading
import queue
from queue import Queue
import os
import time
import shlex
from typing import List, Optional, Tuple, Any, Dict

class RsyncRunner:
    """Handles the execution of rsync commands in a separate thread."""

    def __init__(self, log_queue: Queue[Tuple[str, Any]]) -> None:
        """
        Initializes the RsyncRunner.

        Args:
            log_queue: A queue to send status messages, progress, errors, and completion signals.
                       Messages should be tuples like:
                       ('log', level, message) - e.g., ('log', 'info', 'Starting...')
                       ('progress', current_index, total_count)
                       ('error', error_message)
                       ('finished', success_bool)
        """
        self.log_queue = log_queue
        self.current_process: Optional[subprocess.Popen[str]] = None
        self.interrupted: bool = False
        self._thread: Optional[threading.Thread] = None

    def is_running(self) -> bool:
        """Check if the rsync process is currently running."""
        return self._thread is not None and self._thread.is_alive()

    def interrupt(self) -> None:
        """Signals the running rsync process to stop."""
        self.log_queue.put(('log', 'warning', "Interrupt signal received. Attempting to stop rsync..."))
        self.interrupted = True
        if self.current_process and self.current_process.poll() is None:
            try:
                # Send SIGINT first for graceful shutdown
                self.current_process.terminate()
                self.log_queue.put(('log', 'info', "Sent SIGTERM to rsync process."))
                # Wait a bit, then force kill if necessary
                try:
                    self.current_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.log_queue.put(('log', 'warning', "Rsync did not terminate gracefully, sending SIGKILL."))
                    self.current_process.kill()
            except ProcessLookupError:
                self.log_queue.put(('log', 'warning', "Rsync process already finished."))
            except Exception as e:
                self.log_queue.put(('error', f"Error interrupting process: {e}"))
        else:
             self.log_queue.put(('log', 'info', "No active rsync process to interrupt or already finished."))


    def _build_command(self, base_command: List[str], source: str, destination: str) -> List[str]:
        """Builds the rsync command list."""
        # Simply append source and destination to the base command list
        command = base_command + [source, destination]
        return command

    def _execute_single(self, command: List[str], index: int, total: int) -> bool:
        """Executes a single rsync command."""
        self.log_queue.put(('log', 'info', f"Running command ({index + 1}/{total}): {' '.join(shlex.quote(part) for part in command)}"))
        try:
            # Use Popen for non-blocking execution and capturing output line-by-line
            self.current_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Redirect stderr to stdout
                text=True,
                encoding='utf-8',
                errors='replace', # Handle potential decoding errors
                bufsize=1,  # Line buffered
                universal_newlines=True # Ensure text mode works consistently
            )

            # Read output line by line
            if self.current_process.stdout:
                for line in iter(self.current_process.stdout.readline, ''):
                    if self.interrupted:
                        self.log_queue.put(('log', 'warning', f"Rsync process ({index + 1}/{total}) interrupted by user."))
                        # Attempt termination from the main interrupt logic
                        # self.interrupt() # Called from the main thread
                        return False # Indicate interruption

                    line = line.strip()
                    if line:
                        # Simple progress parsing (customize as needed)
                        if '%' in line and 'to-check=' not in line: # Basic check for progress lines
                             self.log_queue.put(('log', 'progress', line)) # Send raw progress line
                        else:
                             self.log_queue.put(('log', 'info', line))

            # Wait for the process to complete and get the return code
            self.current_process.wait()
            return_code = self.current_process.returncode
            self.current_process = None # Clear the process reference

            if self.interrupted: # Check again after wait() in case interrupt happened late
                 self.log_queue.put(('log', 'warning', f"Rsync process ({index + 1}/{total}) finished after interrupt signal."))
                 return False

            if return_code == 0:
                self.log_queue.put(('log', 'success', f"Command ({index + 1}/{total}) completed successfully."))
                return True
            else:
                self.log_queue.put(('error', f"Command ({index + 1}/{total}) failed with return code {return_code}."))
                return False

        except FileNotFoundError:
            self.log_queue.put(('error', f"Error: '{command[0]}' command not found. Is rsync installed and in your PATH?"))
            self.current_process = None
            return False
        except Exception as e:
            self.log_queue.put(('error', f"An unexpected error occurred during execution ({index + 1}/{total}): {e}"))
            self.current_process = None
            return False


    def run_all(self, sources: List[str], destination: str, start_index: int, base_command: List[str]) -> None:
        """
        Runs rsync for all sources starting from start_index in a background thread.
        """
        if self.is_running():
            self.log_queue.put(('log', 'warning', "Rsync process is already running."))
            return

        self.interrupted = False # Reset interrupt flag

        def _run_in_thread() -> None:
            total_sources = len(sources)
            overall_success = True
            try:
                for i in range(start_index, total_sources):
                    if self.interrupted:
                        self.log_queue.put(('log', 'warning', "Rsync run cancelled due to interrupt."))
                        overall_success = False
                        break

                    source_path = sources[i]
                    self.log_queue.put(('progress', i, total_sources)) # Update progress before starting command

                    # Check if source exists (optional, but good practice)
                    if not os.path.exists(source_path):
                         self.log_queue.put(('error', f"Source path does not exist: {source_path}. Skipping."))
                         # Consider if this should halt the whole process or just skip
                         # For now, let's skip and mark overall as potentially failed if strict=True needed
                         # overall_success = False # Uncomment if skipping should mark failure
                         continue # Skip to the next source

                    try:
                        command = self._build_command(base_command, source_path, destination)
                    except ValueError: # Error building command logged in _build_command
                        overall_success = False
                        break # Stop processing if command build fails

                    success = self._execute_single(command, i, total_sources)
                    if not success:
                        overall_success = False
                        if self.interrupted: # Break if interrupted during execution
                            self.log_queue.put(('log', 'warning', "Stopping further execution due to interrupt."))
                            break
                        else:
                            # Decide whether to continue or stop on error
                            # For now, let's stop on the first error
                            self.log_queue.put(('error', f"Execution failed for {source_path}. Stopping."))
                            break
                    # Small delay between commands (optional)
                    # time.sleep(0.1)

            except Exception as e:
                 self.log_queue.put(('error', f"An unexpected error occurred in the rsync thread: {e}"))
                 overall_success = False
            finally:
                 self.log_queue.put(('finished', overall_success))
                 self.current_process = None # Ensure cleared
                 self._thread = None # Mark thread as finished

        # Start the background thread
        self._thread = threading.Thread(target=_run_in_thread, daemon=True)
        self._thread.start()
        self.log_queue.put(('log', 'info', "Rsync process started in background thread."))