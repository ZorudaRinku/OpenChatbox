import sys
import logging
from config import CONFIG_DIR
from app import create_app


def setup_logging():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)

    logfile = logging.FileHandler(CONFIG_DIR / "openchatbox.log", mode="w", encoding="utf-8")
    logfile.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(logfile)

    logging.getLogger("bleak").setLevel(logging.INFO)


def main():
    setup_logging()
    app, window = create_app()
    window.show()
    sys.exit(app.exec())
                                                                                                                                                                                                                                                            
if __name__ == "__main__":
    main()
