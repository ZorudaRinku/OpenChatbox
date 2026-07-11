"""Shared Linux media helpers - finds the active media player.

A Playing player is preferred; if none, a Paused player is used so that
paused media stays visible.
"""

from __future__ import annotations

import subprocess
import time
from services.platform_info import SUBPROCESS_FLAGS

_cached_player: str | None = None
_cache_time: float = 0
_cache_valid: bool = False


def _find_active_player() -> str | None:
    """Return the best playerctl player: Playing preferred, else Paused."""
    global _cached_player, _cache_time, _cache_valid
    now = time.monotonic()
    if _cache_valid and (now - _cache_time) < 5:
        return _cached_player
    playing = None
    paused = None
    try:
        result = subprocess.run(
            ["playerctl", "--list-all"],
            capture_output=True, text=True, timeout=0.3,
            **SUBPROCESS_FLAGS,
        )
        if result.returncode == 0:
            for player in result.stdout.strip().splitlines():
                try:
                    status = subprocess.run(
                        ["playerctl", "-p", player, "status"],
                        capture_output=True, text=True, timeout=0.3,
                        **SUBPROCESS_FLAGS,
                    )
                    if status.returncode != 0:
                        continue
                    text = status.stdout.strip()
                    if text == "Playing":
                        playing = player
                        break
                    if text == "Paused" and paused is None:
                        paused = player
                except subprocess.TimeoutExpired:
                    continue
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    _cached_player = playing or paused
    _cache_time = now
    _cache_valid = True
    return _cached_player


def playerctl(*args: str) -> subprocess.CompletedProcess:
    """Run a playerctl command against the active player."""
    player = _find_active_player()
    if not player:
        return subprocess.CompletedProcess(args=["playerctl"], returncode=1, stdout="", stderr="")
    cmd = ["playerctl", "-p", player] + list(args)
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=0.3,
        **SUBPROCESS_FLAGS,
    )


def get_timeline() -> tuple[float, float, str] | None:
    """Return (position_secs, duration_secs, status) from the active player."""
    player = _find_active_player()
    if not player:
        return None
    try:
        pos = subprocess.run(
            ["playerctl", "-p", player, "position"],
            capture_output=True, text=True, timeout=0.3,
            **SUBPROCESS_FLAGS,
        )
        length = subprocess.run(
            ["playerctl", "-p", player, "metadata", "mpris:length"],
            capture_output=True, text=True, timeout=0.3,
            **SUBPROCESS_FLAGS,
        )
        status = subprocess.run(
            ["playerctl", "-p", player, "status"],
            capture_output=True, text=True, timeout=0.3,
            **SUBPROCESS_FLAGS,
        )
        if pos.returncode == 0 and length.returncode == 0:
            position = float(pos.stdout.strip())
            duration = float(length.stdout.strip()) / 1_000_000
            status_str = status.stdout.strip().lower() if status.returncode == 0 else ""
            if duration > 0:
                return position, duration, status_str
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None
