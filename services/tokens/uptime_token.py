import time
from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS


class UptimeToken:
    tag = "uptime"
    field_defs = [FieldDef("fallback", "Fallback", "N/A")]
    hint = "System Uptime"

    def resolve(self) -> str:
        seconds = self._get_uptime_seconds()
        if seconds is None:
            return self.fields["fallback"]

        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)

        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        return " ".join(parts)

    def _get_uptime_seconds(self) -> int | None:
        if IS_WINDOWS:
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.GetTickCount64.restype = ctypes.c_uint64
                return int(kernel32.GetTickCount64() / 1000)
            except (AttributeError, OSError):
                return None
        # Linux: read /proc/uptime
        try:
            with open("/proc/uptime") as f:
                return int(float(f.read().split()[0]))
        except OSError:
            return None
