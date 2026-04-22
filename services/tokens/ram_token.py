import psutil
from services.text_processor import FieldDef


class RamToken:
    tag = "ram"
    field_defs = [FieldDef("suffix", "Suffix", "%")]

    def resolve(self) -> str:
        usage = psutil.virtual_memory().percent
        return f"{usage:.0f}{self.fields['suffix']}"
