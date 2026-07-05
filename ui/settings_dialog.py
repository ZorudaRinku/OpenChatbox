from PySide6.QtWidgets import QDialog, QPushButton, QVBoxLayout
from config import (
    CONFIG_PATH,
    ConfigError,
    backup_config,
    list_backups,
    load_config,
    quarantine_corrupt_config,
    restore_backup,
    save_config,
)


class SettingsDialog(QDialog):
    """Application settings window. Options will be added over time."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.main_window = parent
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(360, 280)

        self.layout = QVBoxLayout(self)
        self.layout.addStretch()

        self.restore_btn = QPushButton("Restore Config Backup...")
        self.restore_btn.setToolTip("Restore the config from an earlier backup")
        self.restore_btn.clicked.connect(self.click_restore)
        self.layout.addWidget(self.restore_btn)

    def click_restore(self):
        from ui.restore_dialog import RestoreBackupDialog

        # Flush and snapshot the current state first so the restore is undoable
        if self.main_window is not None:
            self.main_window.save_chats()
        backup_config()

        backups = list_backups()
        if not backups:
            return

        try:
            current_data = CONFIG_PATH.read_bytes()
        except OSError:
            current_data = None
        dlg = RestoreBackupDialog(
            backups, parent=self, startup=False, current_data=current_data
        )
        if not dlg.exec() or dlg.selected_backup is None:
            return

        restore_backup(dlg.selected_backup)
        try:
            new_config = load_config()
        except ConfigError:
            # The chosen backup itself is unreadable. Quarantine it and put
            # the current, still valid state back on disk.
            quarantine_corrupt_config()
            dlg.selected_backup.unlink(missing_ok=True)
            save_config(self.config)
            return

        if self.main_window is not None:
            self.main_window.apply_restored_config(new_config)
