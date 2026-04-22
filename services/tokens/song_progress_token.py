from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS


def _fmt_time(seconds: float) -> str:
    s = int(seconds)
    m, s = divmod(s, 60)
    return f"{m}:{s:02d}"


class SongProgressToken:
    tag = "song_progress"
    field_defs = [
        FieldDef("separator", "Separator", " - "),
        FieldDef("fallback", "Fallback", ""),
    ]
    hint = "<a href=https://github.com/altdesktop/playerctl/issues/359>Using Linux & Browser media?</a>"

    def _get_position_duration(self) -> tuple[float, float] | None:
        if IS_WINDOWS:
            from services.tokens._media_win import _query_media_timeline
            info = _query_media_timeline()
            if info:
                return info["position"], info["duration"]
            return None
        from services.tokens._media_linux import get_position_duration
        return get_position_duration()

    def resolve(self) -> str:
        result = self._get_position_duration()
        if result is None:
            return self.fields["fallback"]
        position, duration = result
        sep = self.fields["separator"]
        return f"{_fmt_time(position)}{sep}{_fmt_time(duration)}"
