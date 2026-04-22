from __future__ import annotations

import subprocess
from typing import Protocol
from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS, SUBPROCESS_FLAGS, session_type, desktop_env, has_cmd


class WindowBackend(Protocol):
    def get_title(self) -> str: ...


class WinBackend:
    """Windows - ctypes call to Win32 API, no extra dependencies."""

    def __init__(self):
        import ctypes
        self._user32 = ctypes.windll.user32
        self._buf_size = 512

    def get_title(self) -> str:
        import ctypes
        hwnd = self._user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(self._buf_size)
        self._user32.GetWindowTextW(hwnd, buf, self._buf_size)
        return buf.value or "Unknown"


class X11Backend:
    """Linux X11 - xdotool."""

    def get_title(self) -> str:
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True, text=True, timeout=2,
            **SUBPROCESS_FLAGS,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return "Unknown"


class HyprlandBackend:
    """Linux Wayland - Hyprland via hyprctl."""

    def get_title(self) -> str:
        import json
        result = subprocess.run(
            ["hyprctl", "activewindow", "-j"],
            capture_output=True, text=True, timeout=2,
            **SUBPROCESS_FLAGS,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("title") or "Unknown"
        return "Unknown"


class SwayBackend:
    """Linux Wayland - Sway/i3 via swaymsg."""

    def get_title(self) -> str:
        import json
        result = subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True, text=True, timeout=2,
            **SUBPROCESS_FLAGS,
        )
        if result.returncode == 0:
            tree = json.loads(result.stdout)
            title = self._find_focused(tree)
            if title:
                return title
        return "Unknown"

    def _find_focused(self, node: dict) -> str | None:
        if node.get("focused") and node.get("name"):
            return node["name"]
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            result = self._find_focused(child)
            if result:
                return result
        return None


class KdotoolBackend:
    """Linux Wayland - KDE via kdotool (optional dependency)."""

    def get_title(self) -> str:
        result = subprocess.run(
            ["kdotool", "getactivewindow", "getwindowname"],
            capture_output=True, text=True, timeout=2,
            **SUBPROCESS_FLAGS,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return "Unknown"


class GnomeBackend:
    """Linux Wayland - GNOME via Shell.Eval DBus."""

    def get_title(self) -> str:
        result = subprocess.run(
            ["dbus-send", "--print-reply", "--dest=org.gnome.Shell",
             "/org/gnome/Shell", "org.gnome.Shell.Eval",
             "string:global.display.get_focus_window().get_title()"],
            capture_output=True, text=True, timeout=2,
            **SUBPROCESS_FLAGS,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith('string "') and line.endswith('"'):
                    title = line[8:-1]
                    if title:
                        return title
        return "Unknown"


class FallbackBackend:
    def get_title(self) -> str:
        return "Unknown"


def _detect_backend() -> WindowBackend:
    if IS_WINDOWS:
        return WinBackend()

    st = session_type()

    if st == "x11":
        if has_cmd("xdotool"):
            return X11Backend()
        return FallbackBackend()

    if st == "wayland":
        de = desktop_env()

        if "hyprland" in de:
            return HyprlandBackend()
        if "sway" in de:
            return SwayBackend()
        if "gnome" in de:
            return GnomeBackend()
        if "kde" in de or "plasma" in de:
            if has_cmd("kdotool"):
                return KdotoolBackend()
            return FallbackBackend()

        # Compositor not identified by env var - check for CLI tools
        if has_cmd("hyprctl"):
            return HyprlandBackend()
        if has_cmd("swaymsg"):
            return SwayBackend()
        if has_cmd("kdotool"):
            return KdotoolBackend()

        return FallbackBackend()

    # Session type unknown - try available tools in order
    if has_cmd("xdotool"):
        return X11Backend()
    if has_cmd("hyprctl"):
        return HyprlandBackend()
    if has_cmd("swaymsg"):
        return SwayBackend()
    if has_cmd("kdotool"):
        return KdotoolBackend()

    return FallbackBackend()


class WindowToken:
    tag = "window"
    field_defs = [FieldDef("fallback", "Fallback", "Unknown")]

    def __init__(self):
        self._backend = _detect_backend()

    def resolve(self) -> str:
        try:
            return self._backend.get_title()
        except Exception:
            return self.fields["fallback"]
