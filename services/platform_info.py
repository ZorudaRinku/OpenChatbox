"""Shared platform detection used by token implementations."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from functools import cache

SYSTEM: str = platform.system()
def _detect_wine() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        import winreg
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Wine").Close()
        return True
    except OSError:
        return False

IS_WINE: bool = _detect_wine()
IS_WINDOWS: bool = SYSTEM == "Windows" and not IS_WINE
IS_LINUX: bool = SYSTEM == "Linux"

SUBPROCESS_FLAGS: dict = (
    {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}
)


@cache
def session_type() -> str:
    """Return the display session type: 'x11', 'wayland', or 'unknown'."""
    return os.environ.get("XDG_SESSION_TYPE", "unknown").lower()


@cache
def desktop_env() -> str:
    """Return the current desktop environment name (lowercase)."""
    return os.environ.get("XDG_CURRENT_DESKTOP", "").lower()


def has_cmd(name: str) -> bool:
    """Check whether a CLI tool is available on PATH."""
    return shutil.which(name) is not None
