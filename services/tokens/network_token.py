import subprocess
from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS, SUBPROCESS_FLAGS


class NetworkToken:
    tag = "network"
    field_defs = [FieldDef("fallback", "Fallback", "Unknown")]

    def resolve(self) -> str:
        if IS_WINDOWS:
            return self._resolve_windows()
        return self._resolve_linux()

    def _resolve_linux(self) -> str:
        # Try nmcli first (NetworkManager)
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "TYPE,NAME", "connection", "show", "--active"],
                capture_output=True, text=True, timeout=2,
                **SUBPROCESS_FLAGS,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        conn_type, name = parts
                        if "wireless" in conn_type or "wifi" in conn_type:
                            return name
                        if "ethernet" in conn_type:
                            return "Ethernet"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        # Fallback: iwgetid
        try:
            result = subprocess.run(
                ["iwgetid", "-r"],
                capture_output=True, text=True, timeout=2,
                **SUBPROCESS_FLAGS,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return self.fields["fallback"]

    def _resolve_windows(self) -> str:
        # Try netsh for Wi-Fi SSID
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=3,
                **SUBPROCESS_FLAGS,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("SSID") and "BSSID" not in line:
                        ssid = line.split(":", 1)[1].strip()
                        if ssid:
                            return ssid
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        # Check if any network adapter is connected (ethernet fallback)
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-NetAdapter | Where-Object {$_.Status -eq 'Up'}).Name"],
                capture_output=True, text=True, timeout=3,
                **SUBPROCESS_FLAGS,
            )
            if result.returncode == 0 and result.stdout.strip():
                name = result.stdout.strip().splitlines()[0]
                return f"Ethernet ({name})" if "ethernet" in name.lower() or "eth" in name.lower() else name
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return self.fields["fallback"]
