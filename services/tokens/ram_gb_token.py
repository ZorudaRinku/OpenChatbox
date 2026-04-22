import psutil
from services.text_processor import FieldDef


class RamGbToken:
    tag = "ramgb"
    field_defs = [FieldDef("suffix", "Suffix", "GB")]

    def resolve(self) -> str:
        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024 ** 3)
        used_gb = mem.used / (1024 ** 3)
        return f"{used_gb:.1f}/{total_gb:.1f} {self.fields['suffix']}"
