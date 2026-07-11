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
        FieldDef("blank_on_paused", "Blank on paused media", "false", field_type="checkbox"),
    ]
    hint = "<a href=https://github.com/altdesktop/playerctl/issues/359>Using Linux & Browser media?</a>"

    def _get_timeline(self) -> tuple[float, float, str] | None:
        if IS_WINDOWS:
            from services.tokens._media_win import _query_media_timeline
            info = _query_media_timeline()
            if info:
                return info["position"], info["duration"], info["status"]
            return None
        from services.tokens._media_linux import get_timeline
        return get_timeline()

    def resolve(self) -> str:
        timeline = self._get_timeline()
        if timeline is None:
            return self.fields["fallback"]
        position, duration, status = timeline
        if self.fields["blank_on_paused"] == "true" and status == "paused":
            return ""
        sep = self.fields["separator"]
        return f"{_fmt_time(position)}{sep}{_fmt_time(duration)}"
