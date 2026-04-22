import subprocess

import psutil
from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS, SUBPROCESS_FLAGS


class CpuTempToken:
    tag = "cpu_temp"
    field_defs = [FieldDef("fallback", "Fallback", "N/A")]

    def resolve(self) -> str:
        if not IS_WINDOWS:
            temps = psutil.sensors_temperatures()
            if temps:
                for name in ("coretemp", "k10temp", "zenpower", "cpu_thermal"):
                    if name in temps and temps[name]:
                        current = temps[name][0].current
                        return f"{current:.0f}°C"
        else:
            try:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance -Namespace root/WMI "
                     "-ClassName MSAcpi_ThermalZoneTemperature "
                     "-ErrorAction SilentlyContinue | "
                     "Select-Object -First 1).CurrentTemperature"],
                    capture_output=True, text=True, timeout=3,
                    **SUBPROCESS_FLAGS,
                )
                if result.returncode == 0 and result.stdout.strip():
                    raw = int(result.stdout.strip())
                    celsius = (raw / 10) - 273.15
                    return f"{celsius:.0f}°C"
            except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
                pass
        return self.fields["fallback"]
