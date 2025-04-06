from dataclasses import dataclass, field
from typing import Optional

@dataclass
class StateManager:
    """Manages the state of the rsync process, particularly for resuming."""
    last_completed_index: int = -1
    was_interrupted: bool = False

    def reset_for_new_run(self) -> None:
        """Resets the state for a completely new rsync run."""
        self.last_completed_index = -1
        self.was_interrupted = False

    def mark_interrupted(self) -> None:
        """Marks the current run as interrupted."""
        self.was_interrupted = True

    def update_completion_index(self, index: int) -> None:
        """Updates the index of the last successfully completed item."""
        # Ensure we only move forward or stay put, never backward.
        if index > self.last_completed_index:
            self.last_completed_index = index

    def can_resume(self, total_items: int) -> bool:
        """
        Checks if a resume operation is possible and meaningful.
        Resume is possible if the process was interrupted and there are items
        remaining that were not completed.
        """
        return (
            self.was_interrupted and
            0 <= self.last_completed_index < (total_items - 1)
        )

    def get_resume_start_index(self) -> int:
        """
        Determines the starting index for a resume operation.
        If a resume is possible, it starts from the item after the last completed one.
        Otherwise, it starts from the beginning (index 0).
        """
        if self.was_interrupted and self.last_completed_index >= -1:
            return self.last_completed_index + 1
        return 0