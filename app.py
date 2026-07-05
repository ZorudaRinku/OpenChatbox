import sys
import logging
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow
from services.osc import OSCClient
from config import (
    CONFIG_PATH,
    ConfigError,
    list_backups,
    load_config,
    quarantine_corrupt_config,
    restore_backup,
)
from services.text_processor import TextProcessor, init_fields
from services.tokens import ALL_TOKENS
from services.platform_info import SYSTEM, IS_WINE
from services import vrchat_service
import resources_rc

VERSION = "0.0.0+dev"

logger = logging.getLogger(__name__)

try:
    from ctypes import windll
    windll.shell32.SetCurrentProcessExplicitAppUserModelID("OpenChatbox.OpenChatbox.1.0")
except (ImportError, AttributeError):
    pass

def _recover_config():
    """Handle an unreadable config.toml: quarantine it, offer backups, fall back to defaults."""
    from ui.restore_dialog import RestoreBackupDialog

    quarantine_corrupt_config()
    backups = list_backups()
    if not backups:
        QMessageBox.warning(
            None,
            "OpenChatbox",
            "Your config file could not be read and no backups were found.\n"
            "The corrupted file was saved to the Backups folder and default "
            "settings will be used.",
        )
        return load_config()

    error = None
    while True:
        dialog = RestoreBackupDialog(backups, error=error)
        if not dialog.exec() or dialog.selected_backup is None:
            logger.warning("User declined backup restore, using defaults")
            return load_config()

        restore_backup(dialog.selected_backup)
        try:
            return load_config()
        except ConfigError:
            logger.warning("Restored backup %s could not be read", dialog.selected_backup)
            CONFIG_PATH.unlink(missing_ok=True)
            error = "Backup failed to restore, pick another or check log/backup file."


def create_app():
    app = QApplication(sys.argv)
    app.setApplicationName("OpenChatbox")
    app.setDesktopFileName("openchatbox")
    app.setWindowIcon(QIcon(":/OpenChatbox.png"))
    logger.info("OpenChatbox %s on %s%s", VERSION, SYSTEM, " (wine)" if IS_WINE else "")
    try:
        config = load_config()
    except ConfigError:
        config = _recover_config()
    logger.info("OSC target %s:%s", config["osc"]["ip"], config["osc"]["port"])
    osc_client = OSCClient(config["osc"]["ip"], config["osc"]["port"])
    vrchat_service.bootstrap_from_config(config)

    token_configs = config.get("tokens", {})
    text_processor = TextProcessor()
    text_processor.preserve_blank_lines = bool(
        config.get("settings", {}).get("preserve_blank_lines", False)
    )
    for token_cls in ALL_TOKENS:
        token = token_cls()
        init_fields(token, token_configs.get(token.tag))
        text_processor.register(token)

    logger.info("Registered %d tokens", len(text_processor.tokens))
    window = MainWindow(osc_client, config, text_processor=text_processor)
    return app, window