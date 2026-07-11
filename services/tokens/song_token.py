import subprocess

from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS


class SongToken:
    tag = "song"
    field_defs = [
        FieldDef("fallback", "Fallback", "Unknown"),
        FieldDef("blank_on_paused", "Blank on paused media", "false", field_type="checkbox"),
    ]
    hint = "<a href=https://github.com/altdesktop/playerctl/issues/359>Using Linux & Browser media?</a>"

    def resolve(self) -> str:
        blank_paused = self.fields["blank_on_paused"] == "true"
        if IS_WINDOWS:
            from services.tokens._media_win import _query_media_session
            info = _query_media_session()
            if info and info["title"]:
                if blank_paused and info["status"] == "paused":
                    return ""
                return info["title"]
            return self.fields["fallback"]
        from services.tokens._media_linux import playerctl
        try:
            result = playerctl("metadata", "--format", "{{status}}\n{{title}}")
            if result.returncode == 0 and result.stdout.strip():
                status, _, title = result.stdout.strip().partition("\n")
                if title:
                    if blank_paused and status.lower() == "paused":
                        return ""
                    return title
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return self.fields["fallback"]
