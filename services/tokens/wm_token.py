import os
import subprocess
from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS, IS_LINUX, SUBPROCESS_FLAGS


class WmToken:
    tag = "wm"
    field_defs = [FieldDef("fallback", "Fallback", "Unknown")]
    hint = "Window Manager"

    def resolve(self) -> str:
        if IS_WINDOWS:
            return "DWM"

        if not IS_LINUX:
            return self.fields["fallback"]

        # Check common env vars
        for var in ("HYPRLAND_INSTANCE_SIGNATURE", ):
            if os.environ.get(var):
                return "Hyprland"

        if os.environ.get("SWAYSOCK"):
            return "Sway"

        if os.environ.get("I3SOCK"):
            return "i3"

        # Try wmctrl
        try:
            result = subprocess.run(
                ["wmctrl", "-m"],
                capture_output=True, text=True, timeout=2,
                **SUBPROCESS_FLAGS,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith("Name:"):
                        return line.split(":", 1)[1].strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: XDG_CURRENT_DESKTOP often hints at WM
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
        if desktop:
            return desktop

        return self.fields["fallback"]
