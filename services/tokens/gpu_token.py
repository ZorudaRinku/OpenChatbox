from services.gpu_info import available_gpus, get_utilization
from services.text_processor import FieldDef


class GpuToken:
    tag = "gpu"
    field_defs = [
        FieldDef("gpu", "GPU", "Auto", field_type="dropdown",
                 options=available_gpus()),
        FieldDef("suffix", "Suffix", "%"),
        FieldDef("fallback", "Fallback", "N/A"),
    ]

    def resolve(self) -> str:
        val = get_utilization(self.fields["gpu"])
        if val is not None:
            return f"{val}{self.fields['suffix']}"
        return self.fields["fallback"]
