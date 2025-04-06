# config.py
from typing import List

# Base rsync command options (source and destination added later)
# Note: This is now just the options part, not the full command string
RSYNC_BASE_COMMAND: List[str] = [
    "rsync",
    "-rltvD",          # Recursive, links, times, verbose, devices, specials
    "--info=progress2", # Show overall progress
    "--times",         # Preserve modification times
    "--atimes",        # Preserve access times
    "--crtimes",       # Preserve creation times (if supported)
    "--omit-dir-times",# Omit directory times
    # Add other desired default flags here, e.g.:
    # "--delete",      # Delete extraneous files from dest dirs (use with caution!)
    # "--dry-run",     # Perform a trial run with no changes made
]

# You could add other configuration variables here later if needed
# e.g., DEFAULT_LOG_LEVEL = "INFO"