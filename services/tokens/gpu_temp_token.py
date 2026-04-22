from services.gpu_info import available_gpus, get_temperature
from services.text_processor import FieldDef


class GpuTempToken:
    tag = "gpu_temp"
    field_defs = [
        FieldDef("gpu", "GPU", "Auto", field_type="dropdown",
                 options=available_gpus()),
        FieldDef("fallback", "Fallback", "N/A"),
    ]

    def resolve(self) -> str:
        val = get_temperature(self.fields["gpu"])
        if val is not None:
            return f"{val}°C"
        return self.fields["fallback"]
