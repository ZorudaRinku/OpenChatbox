import psutil
from services.text_processor import FieldDef


class BatteryToken:
    tag = "battery"
    field_defs = [
        FieldDef("plugged", "Plugged Icon", "⚡"),
        FieldDef("unplugged", "Unplugged Icon", "🔋"),
        FieldDef("fallback", "Fallback", "N/A"),
    ]

    def resolve(self) -> str:
        bat = psutil.sensors_battery()
        if bat is None:
            return self.fields["fallback"]
        status = self.fields["plugged"] if bat.power_plugged else self.fields["unplugged"]
        return f"{bat.percent:.0f}% {status}"
