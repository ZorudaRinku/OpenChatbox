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
    ]
    hint = "<a href=https://github.com/altdesktop/playerctl/issues/359>Using Linux & Browser media?</a>"

    def _get_progress(self) -> float | None:
        if IS_WINDOWS:
            from services.tokens._media_win import _query_media_timeline
            info = _query_media_timeline()
            if info and info["duration"] > 0:
                return info["position"] / info["duration"]
            return None
        from services.tokens._media_linux import get_position_duration
        result = get_position_duration()
        if result:
            return result[0] / result[1]
        return None

    def resolve(self) -> str:
        progress = self._get_progress()
        if progress is None:
            return self.fields["fallback"]
        progress = max(0.0, min(1.0, progress))
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
