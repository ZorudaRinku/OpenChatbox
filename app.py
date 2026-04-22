import sys
import logging
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from services.osc import OSCClient
from config import load_config
from services.text_processor import TextProcessor, init_fields
from services.tokens import ALL_TOKENS
import resources_rc

VERSION = "0.0.0+dev"

logger = logging.getLogger(__name__)

try:
    from ctypes import windll
    windll.shell32.SetCurrentProcessExplicitAppUserModelID("OpenChatbox.OpenChatbox.1.0")
except (ImportError, AttributeError):
    pass

def create_app():
    app = QApplication(sys.argv)
    app.setApplicationName("OpenChatbox")
    app.setDesktopFileName("openchatbox")
    app.setWindowIcon(QIcon(":/OpenChatbox.png"))
    config = load_config()
    logger.info("OSC target %s:%s", config["osc"]["ip"], config["osc"]["port"])
    osc_client = OSCClient(config["osc"]["ip"], config["osc"]["port"])

    token_configs = config.get("tokens", {})
    text_processor = TextProcessor()
    for token_cls in ALL_TOKENS:
        token = token_cls()
        init_fields(token, token_configs.get(token.tag))
        text_processor.register(token)

    logger.info("Registered %d tokens", len(text_processor.tokens))
    window = MainWindow(osc_client, config, text_processor=text_processor)
    return app, window