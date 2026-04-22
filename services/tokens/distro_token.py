import platform
from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS, IS_LINUX


class DistroToken:
    tag = "distro"
    field_defs = []
    hint = "Operating System Distrobution"

    def resolve(self) -> str:
        if IS_LINUX:
            try:
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            return line.split("=", 1)[1].strip().strip('"')
            except OSError:
                pass
        if IS_WINDOWS:
            ver = platform.version()
            release = platform.release()
            return f"Windows {release} ({ver})"
        return platform.system()
