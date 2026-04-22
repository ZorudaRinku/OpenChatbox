import subprocess
from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS, SUBPROCESS_FLAGS


class PingToken:
    tag = "ping"
    field_defs = [
        FieldDef("target", "Target", "8.8.8.8"),
        FieldDef("suffix", "Suffix", "ms"),
        FieldDef("fallback", "Fallback", "N/A"),
    ]

    def resolve(self) -> str:
        try:
            if IS_WINDOWS:
                cmd = ["ping", "-n", "1", "-w", "2000", self.fields["target"]]
            else:
                cmd = ["ping", "-c", "1", "-W", "2", self.fields["target"]]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=3,
                **SUBPROCESS_FLAGS,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "time=" in line or "time<" in line:
                        # Linux: "time=12.3 ms", Windows: "time=12ms" or "time<1ms"
                        chunk = line.split("time")[1]
                        ms = chunk.lstrip("=<").split("m")[0].strip()
                        return f"{ms} {self.fields['suffix']}"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return self.fields["fallback"]
