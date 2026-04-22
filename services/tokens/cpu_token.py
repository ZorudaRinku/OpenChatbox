import psutil
from services.text_processor import FieldDef


class CpuToken:
    tag = "cpu"
    field_defs = [FieldDef("suffix", "Suffix", "%")]

    def resolve(self) -> str:
        usage = psutil.cpu_percent(interval=None)
        return f"{usage:.0f}{self.fields['suffix']}"
