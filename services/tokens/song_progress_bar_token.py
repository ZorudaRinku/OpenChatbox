from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS


class SongProgressBarToken:
    tag = "song_progress_bar"
    field_defs = [
        FieldDef("fill", "Fill", "█"),
        FieldDef("empty", "Empty", "▒"),
        FieldDef("indicator", "Indicator", ""),
        FieldDef("width", "Width", "14", field_type="spinbox"),
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
        if duration <= 0:
            return self.fields["fallback"]
        progress = max(0.0, min(1.0, position / duration))
        try:
            width = int(self.fields["width"])
        except ValueError:
            width = 10
        width = max(1, width)
        fill = self.fields["fill"]
        empty = self.fields["empty"]
        indicator = self.fields["indicator"]
        pos = int(progress * width)
        pos = min(pos, width - 1)
        return fill * pos + indicator + empty * (width - 1 - pos)
