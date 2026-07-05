from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
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

        osc = config.get("osc", {})
        target_box = QWidget()
        target_box.setToolTip(
            "IP Address and port of the OSC receiver chat messages are sent to.\n"
            "For this PC, Use 127.0.0.1 and port 9000.\n"
            "For quest standalone, use IP & port of headset."
        )
        target_layout = QVBoxLayout(target_box)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.addWidget(QLabel("OSC Target IP/Port"))
        target_row = QHBoxLayout()
        self.address_edit = QLineEdit(str(osc.get("ip", "127.0.0.1")))
        self.address_edit.setPlaceholderText("Address")
        self.address_edit.editingFinished.connect(self.apply_osc_target)
        target_row.addWidget(self.address_edit, 1)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(int(osc.get("port", 9000)))
        self.port_spin.valueChanged.connect(self.apply_osc_target)
        target_row.addWidget(self.port_spin)
        target_layout.addLayout(target_row)
        self.layout.addWidget(target_box)

        self.preserve_blank_lines_cb = QCheckBox("Preserve Blank Lines")
        self.preserve_blank_lines_cb.setToolTip(
            "Keep blank lines in messages instead of removing them before sending"
        )
        self.preserve_blank_lines_cb.setChecked(
            bool(config.get("settings", {}).get("preserve_blank_lines", False))
        )
        self.preserve_blank_lines_cb.toggled.connect(self.toggle_preserve_blank_lines)
        self.layout.addWidget(self.preserve_blank_lines_cb)

        self.layout.addStretch()

        self.restore_btn = QPushButton("Restore Config Backup...")
        self.restore_btn.setToolTip("Restore the config from an earlier backup")
        self.restore_btn.clicked.connect(self.click_restore)
        self.layout.addWidget(self.restore_btn)

    def apply_osc_target(self):
        osc = self.config.setdefault("osc", {})
        ip = self.address_edit.text().strip()
        if not ip:
            # Ignore an empty address and put the current value back
            self.address_edit.setText(str(osc.get("ip", "127.0.0.1")))
            return
        port = self.port_spin.value()
        if osc.get("ip") == ip and osc.get("port") == port:
            return
        osc["ip"] = ip
        osc["port"] = port
        save_config(self.config)
        if self.main_window is not None:
            self.main_window.set_osc_target(ip, port)

    def toggle_preserve_blank_lines(self, checked):
        self.config.setdefault("settings", {})["preserve_blank_lines"] = bool(checked)
        save_config(self.config)
        if self.main_window is not None and self.main_window.text_processor:
            self.main_window.text_processor.preserve_blank_lines = bool(checked)
            self.main_window.revalidate_all()

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

        # Refresh the OSC target fields from the restored config
        osc = self.config.get("osc", {})
        self.address_edit.blockSignals(True)
        self.address_edit.setText(str(osc.get("ip", "127.0.0.1")))
        self.address_edit.blockSignals(False)
        self.port_spin.blockSignals(True)
        self.port_spin.setValue(int(osc.get("port", 9000)))
        self.port_spin.blockSignals(False)
