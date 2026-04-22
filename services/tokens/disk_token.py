import psutil
from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS

_DEFAULT_PATH = "C:\\" if IS_WINDOWS else "/"


class DiskToken:
    tag = "disk"
    field_defs = [
        FieldDef("path", "Mount Path", _DEFAULT_PATH),
        FieldDef("suffix", "Suffix", "GB"),
    ]

    def resolve(self) -> str:
        usage = psutil.disk_usage(self.fields["path"])
        used_gb = usage.used / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        return f"{used_gb:.1f}/{total_gb:.1f} {self.fields['suffix']} ({usage.percent}%)"
