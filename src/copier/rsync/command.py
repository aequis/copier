# src/copier/rsync/command.py
"""
Builds the rsync command arguments based on selected options.
"""

import typing

class RsyncCommandBuilder:
    """
    Constructs the list of command-line arguments for the rsync executable
    based on a dictionary of options.
    """

    def build_command(self, options: typing.Dict[str, bool]) -> typing.List[str]:
        """
        Builds the rsync command list from the provided options.

        Args:
            options: A dictionary where keys are rsync option names (e.g.,
                     'archive', 'compress', 'delete', 'verbose', 'progress',
                     'dry_run', 'preserve_permissions', 'human') and values
                     are booleans indicating if the option is enabled.

        Returns:
            A list of strings representing the rsync command and its arguments,
            ready to be prepended to source(s) and destination.
        """
        command = ["rsync"]
        selected_options = options # Use the provided options dictionary

        if selected_options.get("archive", False):
            command.append("-a") # Archive implies -rlptgoD, including permissions
            # Note: If -a is checked, the "preserve_permissions" checkbox is effectively ignored
            # because -a forces permission preservation.
        else:
            # Build flags individually if archive is off
            command.extend(["-rltD"]) # Base flags: Recursive, links, times, devices/specials
            if selected_options.get("preserve_permissions", False):
                command.extend(["-pgo"]) # Add permissions, group, owner
            # Add other time flags (these might be redundant with -t in -rltD but explicit doesn't hurt)
            # Consider if these are always desired or should be options
            command.extend(["--atimes", "--crtimes", "--omit-dir-times"])

        if selected_options.get("verbose", False):
            command.append("-v")

        if selected_options.get("compress", False):
            command.append("-z")

        if selected_options.get("human", False):
            command.append("-h")

        if selected_options.get("progress", False):
            command.append("--progress")
        else:
            # Use info=progress2 if --progress is not selected (similar to original base)
            command.append("--info=progress2")

        if selected_options.get("delete", False):
            command.append("--delete")

        if selected_options.get("dry_run", False):
            command.append("-n")

        # Remove duplicates just in case (e.g., if -a and -v are added)
        # Note: Order might matter for some flags, but this simple approach should be okay here.
        # A more robust way might be needed if complex flag interactions arise.
        # Using dict.fromkeys preserves order in Python 3.7+
        command = list(dict.fromkeys(command))

        # The actual source and destination will be added later by the caller
        # (RsyncProcessManager) before executing the command.
        return command