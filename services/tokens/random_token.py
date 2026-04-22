import random
import time
from services.text_processor import FieldDef


class RandomToken:
    tag = "random"
    field_defs = [
        FieldDef("min", "Min", "0", field_type="spinbox"),
        FieldDef("max", "Max", "100", field_type="spinbox"),
        FieldDef("delay", "Hold (seconds)", "0", field_type="spinbox"),
    ]

    def __init__(self):
        self._value: int | None = None
        self._rolled_at: float = 0.0

    def resolve(self) -> str:
        try:
            lo = int(self.fields.get("min", "0"))
            hi = int(self.fields.get("max", "100"))
        except ValueError:
            return "?"
        if lo > hi:
            lo, hi = hi, lo

        try:
            delay = float(self.fields.get("delay", "0"))
        except ValueError:
            delay = 0.0

        now = time.monotonic()
        if self._value is None or (now - self._rolled_at) >= delay:
            self._value = random.randint(lo, hi)
            self._rolled_at = now

        return str(self._value)
