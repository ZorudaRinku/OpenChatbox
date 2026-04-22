from datetime import datetime
from services.text_processor import FieldDef


class CountdownToken:
    tag = "countdown"
    field_defs = [FieldDef("target", "Target Time (HH:MM)", "00:00")]

    def __init__(self):
        self._blink = False

    def resolve(self) -> str:
        raw = self.fields.get("target", "00:00").strip()
        try:
            target = datetime.strptime(raw, "%H:%M").time()
        except ValueError:
            return "??:??"
        now = datetime.now()
        target_dt = now.replace(
            hour=target.hour, minute=target.minute, second=0, microsecond=0,
        )
        diff = int((target_dt - now).total_seconds())
        if diff <= 0:
            if diff < -3600:
                # More than 1 hour past - wrap to next day
                diff += 86400
            else:
                self._blink = not self._blink
                return "-:--" if self._blink else "0:00"
        hours, remainder = divmod(diff, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
