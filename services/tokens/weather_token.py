import locale
import logging
import threading
import time
import urllib.request
from services.text_processor import FieldDef

logger = logging.getLogger(__name__)


class WeatherToken:
    tag = "weather"
    field_defs = [FieldDef("fallback", "Fallback", "N/A")]
    hint = "Uses wttr.in Service"

    def __init__(self):
        self._cache: str | None = None
        self._last_fetch: float = 0
        self._fetching = False

    @staticmethod
    def _is_us_locale() -> bool:
        loc = locale.getlocale()[0] or ""
        return loc.endswith("_US") or loc.startswith("en_US")

    @staticmethod
    def _c_to_f(text: str) -> str:
        """Convert '...+2°C' or '...-5°C' to Fahrenheit."""
        import re
        def _replace(m: re.Match) -> str:
            c = int(m.group(1))
            f = round(c * 9 / 5 + 32)
            return f"{'+' if f >= 0 else ''}{f}°F"
        return re.sub(r'([+-]?\d+)°C', _replace, text)

    def _fetch(self):
        try:
            url = "https://wttr.in/?format=%c+%t"
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                text = resp.read().decode().strip()
                if text:
                    if self._is_us_locale():
                        text = self._c_to_f(text)
                    self._cache = text
        except Exception:
            logger.exception("Weather fetch failed")
        finally:
            self._fetching = False

    def resolve(self) -> str:
        now = time.monotonic()
        if (now - self._last_fetch) >= 600 and not self._fetching:
            self._last_fetch = now
            self._fetching = True
            threading.Thread(target=self._fetch, daemon=True).start()
        return self._cache or self.fields["fallback"]
