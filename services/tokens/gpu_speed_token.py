from services.gpu_info import available_gpus, get_clock
from services.text_processor import FieldDef


class GpuSpeedToken:
    tag = "gpuspeed"
    field_defs = [
        FieldDef("gpu", "GPU", "Auto", field_type="dropdown",
                 options=available_gpus()),
        FieldDef("suffix", "Suffix", "MHz"),
        FieldDef("fallback", "Fallback", "N/A"),
    ]

    def resolve(self) -> str:
        val = get_clock(self.fields["gpu"])
        if val is not None:
            return f"{val} {self.fields['suffix']}"
        return self.fields["fallback"]
