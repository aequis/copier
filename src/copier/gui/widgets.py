# src/copier/gui/widgets.py
from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui
from PySide6.QtCore import Signal, Slot, Qt, QUrl, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPalette, QColor
from PySide6.QtWidgets import (
    QLineEdit, QListWidget, QAbstractItemView, QWidget
)

class DropLineEdit(QLineEdit):
    """Custom QLineEdit that accepts file/folder drops."""
    dropped = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        # Make it look read-only but still accept drops
        self.setReadOnly(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(Qt.GlobalColor.lightGray).lighter(120))
        self.setPalette(palette)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            # Check if it's a single directory
            urls = event.mimeData().urls()
            if len(urls) == 1:
                local_path = urls[0].toLocalFile()
                if QtCore.QFileInfo(local_path).isDir():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                local_path = urls[0].toLocalFile()
                if QtCore.QFileInfo(local_path).isDir():
                    self.setText(local_path)
                    self.dropped.emit(local_path)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def setText(self, text: str) -> None:
        """Override setText to ensure read-only appearance is maintained."""
        super().setText(text)
        # Force re-evaluation of read-only state visually if needed
        self.setReadOnly(True)


class DropListWidget(QListWidget):
    """Custom QListWidget that accepts file/folder drops."""
    items_dropped = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) # Allow multi-select

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            dropped_paths = []
            for url in event.mimeData().urls():
                local_path = url.toLocalFile()
                if local_path: # Ensure path is valid
                    # Avoid adding duplicates
                    if not self.findItems(local_path, Qt.MatchFlag.MatchExactly):
                        self.addItem(local_path)
                        dropped_paths.append(local_path)
            if dropped_paths:
                self.items_dropped.emit(dropped_paths)
            event.acceptProposedAction()
        else:
            event.ignore()