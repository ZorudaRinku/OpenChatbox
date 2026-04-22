import time
from services.text_processor import FieldDef


class SessionToken:
    tag = "session"
    field_defs = []
    hint = "Session Duration"

    def __init__(self):
        self._start = time.monotonic()

    def resolve(self) -> str:
        elapsed = int(time.monotonic() - self._start)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
