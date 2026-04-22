import subprocess

from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS


class NowPlayingToken:
    tag = "nowplaying"
    field_defs = [
        FieldDef("format", "Format", "{{title}} - {{artist}}"),
        FieldDef("playing_prefix", "Playing Prefix", "▶️"),
        FieldDef("paused_prefix", "Paused Prefix", "⏸️"),
        FieldDef("fallback", "Fallback", ""),
        FieldDef("max_length", "Max Length (0 = off)", "0", field_type="spinbox"),
    ]
    hint = "<a href=https://github.com/altdesktop/playerctl/issues/359>Using Linux & Browser media?</a>"

    def _truncate(self, text: str) -> str:
        limit = int(self.fields["max_length"])
        if limit > 0 and len(text) > limit:
            return text[:limit]
        return text

    def resolve(self) -> str:
        if IS_WINDOWS:
            return self._resolve_windows()
        return self._resolve_linux()

    def _resolve_linux(self) -> str:
        from services.tokens._media_linux import playerctl
        try:
            combined_fmt = "{{status}}\n" + self.fields["format"]
            result = playerctl("metadata", "--format", combined_fmt)
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split("\n", 1)
                status = lines[0].lower()
                text = lines[1] if len(lines) > 1 else ""
                if text:
                    prefix = self.fields["paused_prefix"] if status == "paused" else self.fields["playing_prefix"]
                    return self._truncate(f"{prefix} {text}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return self.fields["fallback"]

    def _resolve_windows(self) -> str:
        from services.tokens._media_win import _query_media_session
        info = _query_media_session()
        if info and (info["artist"] or info["title"]):
            text = self.fields["format"]
            text = text.replace("{{artist}}", info["artist"] or "Unknown")
            text = text.replace("{{title}}", info["title"] or "Unknown")
            if info["status"] == "paused":
                prefix = self.fields["paused_prefix"]
            else:
                prefix = self.fields["playing_prefix"]
            return self._truncate(f"{prefix} {text}")
        return self.fields["fallback"]
