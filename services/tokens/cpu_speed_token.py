import psutil
from services.text_processor import FieldDef


class CpuSpeedToken:
    tag = "cpuspeed"
    field_defs = [
        FieldDef("suffix", "Suffix", "GHz"),
        FieldDef("fallback", "Fallback", "N/A"),
    ]

    def resolve(self) -> str:
        freq = psutil.cpu_freq()
        if freq and freq.current:
            ghz = freq.current / 1000
            return f"{ghz:.2f} {self.fields['suffix']}"
        return self.fields["fallback"]
