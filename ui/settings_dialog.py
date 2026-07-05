from PySide6.QtWidgets import QDialog, QVBoxLayout


class SettingsDialog(QDialog):
    """Application settings window. Options will be added over time."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(360, 280)

        self.layout = QVBoxLayout(self)
        self.layout.addStretch()
