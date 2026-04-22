import logging
import threading
import time
import urllib.parse
import urllib.request
from services.text_processor import FieldDef

logger = logging.getLogger(__name__)


class TwitchViewersToken:
    tag = "twitch_viewers"
    field_defs = [
        FieldDef("channel", "Channel", ""),
        FieldDef("fallback", "Fallback", "N/A"),
    ]
    hint = "Uses DecAPI Service"

    def __init__(self):
        self._cache: str | None = None
        self._last_fetch: float = 0
        self._fetching = False
        self._last_channel: str = ""

    def _fetch(self):
        try:
            channel = self.fields.get("channel", "").strip()
            if not channel:
                return
            url = f"https://decapi.me/twitch/viewercount/{urllib.parse.quote(channel, safe='')}"
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                text = resp.read().decode().strip()
                if text and text.isdigit():
                    self._cache = text
                elif "offline" in text.lower():
                    self._cache = "offline"
        except Exception:
            logger.exception("Twitch viewer count fetch failed")
        finally:
            self._fetching = False

    def resolve(self) -> str:
        if not self.fields.get("channel", "").strip():
            return self.fields["fallback"]
        channel = self.fields.get("channel", "").strip()
        if channel != self._last_channel:
            self._last_channel = channel
            self._cache = None
            self._last_fetch = 0
        now = time.monotonic()
        if (now - self._last_fetch) >= 60 and not self._fetching:
            self._last_fetch = now
            self._fetching = True
            threading.Thread(target=self._fetch, daemon=True).start()
        return self._cache or self.fields["fallback"]
