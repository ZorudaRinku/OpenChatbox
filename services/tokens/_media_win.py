from __future__ import annotations
import asyncio
import logging

logger = logging.getLogger(__name__)

_winrt_available: bool | None = None


def _check_winrt() -> bool:
    """Check winrt availability once and cache the result."""
    global _winrt_available
    if _winrt_available is not None:
        return _winrt_available
    try:
        from winrt.windows.media.control import (  # noqa: F401
            GlobalSystemMediaTransportControlsSessionManager,
        )
        _winrt_available = True
    except ImportError:
        logger.warning(
            "winrt media control package not found. "
            "Install with: pip install winrt-runtime winrt-Windows.Media.Control"
        )
        _winrt_available = False
    return _winrt_available


def _run_async(coro):
    """Run a WinRT coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _get_media_info() -> dict[str, str] | None:
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager
    manager = await SessionManager.request_async()
    session = manager.get_current_session()
    if not session:
        logger.debug("No active media session found")
        return None
    info = await session.try_get_media_properties_async()
    status = session.get_playback_info().playback_status
    # playback_status is an enum; 4 = Playing, 5 = Paused
    status_str = "playing" if status == 4 else "paused" if status == 5 else str(status)
    return {
        "artist": info.artist or "",
        "title": info.title or "",
        "status": status_str,
    }


def _query_media_session() -> dict[str, str] | None:
    if not _check_winrt():
        return None
    try:
        return _run_async(_get_media_info())
    except Exception:
        logger.exception("Failed to query Windows media session")
        return None


def _timespan_to_seconds(ts) -> float:
    """Convert a WinRT TimeSpan to seconds (handles v1 and v2)."""
    if hasattr(ts, "total_seconds"):
        return ts.total_seconds()
    return getattr(ts, "duration", 0) / 1e7


async def _get_media_timeline() -> dict[str, float] | None:
    import datetime
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager
    manager = await SessionManager.request_async()
    session = manager.get_current_session()
    if not session:
        return None
    timeline = session.get_timeline_properties()
    position = _timespan_to_seconds(timeline.position)
    duration = _timespan_to_seconds(timeline.end_time)
    if duration <= 0:
        return None
    # Browsers only update the timeline on play/pause/seek, so the
    # reported position goes stale while playing. Extrapolate forward
    # using last_updated_time (UTC datetime) and playback_rate.
    info = session.get_playback_info()
    rate = info.playback_rate if info.playback_rate is not None else 0.0
    if rate > 0:
        last_updated = timeline.last_updated_time
        if last_updated is not None:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            try:
                elapsed = (now_utc - last_updated).total_seconds()
            except TypeError:
                # Timezone-naive datetime from older winrt versions
                elapsed = (now_utc - last_updated.replace(
                    tzinfo=datetime.timezone.utc
                )).total_seconds()
            if elapsed > 0:
                position = min(position + elapsed * rate, duration)
    return {"position": position, "duration": duration}


def _query_media_timeline() -> dict[str, float] | None:
    if not _check_winrt():
        return None
    try:
        return _run_async(_get_media_timeline())
    except Exception:
        logger.exception("Failed to query Windows media timeline")
        return None
