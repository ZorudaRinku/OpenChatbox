import re
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class RestoreBackupDialog(QDialog):
    """Modal offering to restore a config backup.

    Shown at startup when config.toml cannot be read (startup=True) or
    on demand from the settings window (startup=False).

    current_data, when given, holds the bytes of the config currently in
    use; backups identical to it are marked as "current".
    """

    def __init__(self, backups, parent=None, startup=True, error=None, current_data=None):
        super().__init__(parent)
        self.setWindowTitle("Restore Config Backup")
        self.setModal(True)
        self.selected_backup = None

        if startup:
            message = (
                "Your config file could not be read and may be corrupted.\n"
                "A copy of the corrupted file has been saved to the Backups folder.\n\n"
                "Select a backup to restore, or continue with default settings."
            )
            reject_text = "Use Defaults"
        else:
            message = (
                "Select a backup to restore.\n"
                "Your current config is backed up first, so a restore can be undone."
            )
            reject_text = "Cancel"

        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)

        if error:
            error_label = QLabel(error)
            error_label.setWordWrap(True)
            error_label.setStyleSheet("color: #d9534f;")
            layout.addWidget(error_label)

        self.list = QListWidget()
        for path in backups:
            label = self._label_for(path)
            is_current = self._is_current(path, current_data)
            if is_current:
                label += "  - current"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            if is_current:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(self._accept_item)
        layout.addWidget(self.list)

        buttons = QDialogButtonBox()
        buttons.addButton("Restore Selected", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(reject_text, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._accept_current)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.resize(420, 300)

    @staticmethod
    def _is_current(path: Path, current_data) -> bool:
        if current_data is None:
            return False
        try:
            return path.read_bytes() == current_data
        except OSError:
            return False

    @staticmethod
    def _label_for(path: Path) -> str:
        match = re.match(r"config-(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})", path.stem)
        if match:
            date, h, m, s = match.groups()
            stamp = f"{date} {h}:{m}:{s}"
        else:
            stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        size_kb = max(1, path.stat().st_size // 1024)
        return f"{stamp}  ({size_kb} KB)"

    def _accept_item(self, item):
        self.selected_backup = Path(item.data(Qt.ItemDataRole.UserRole))
        self.accept()

    def _accept_current(self):
        item = self.list.currentItem()
        if item is None:
            return
        self._accept_item(item)
