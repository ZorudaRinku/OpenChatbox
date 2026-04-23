import json
import logging
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

LATEST_URL = "https://api.github.com/repos/ZorudaRinku/OpenChatbox/releases/latest"
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def parse_version(v: str) -> tuple[int, int, int]:
    m = _VERSION_RE.match(v)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def fetch_latest_tag(timeout: float = 5.0) -> str | None:
    try:
        req = Request(LATEST_URL, headers={"User-Agent": "OpenChatbox"})
        with urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
            return data.get("tag_name")
    except (URLError, OSError, ValueError) as e:
        logger.info("Update check failed: %s", e)
        return None


class UpdateChecker(QObject):
    update_available = Signal(str)
    finished = Signal()

    def __init__(self, current_version: str):
        super().__init__()
        self.current = current_version

    def run(self):
        if "dev" in self.current:
            self.finished.emit()
            return
        latest = fetch_latest_tag()
        if latest and parse_version(latest) > parse_version(self.current):
            self.update_available.emit(latest)
        self.finished.emit()
