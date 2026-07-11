import subprocess

from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS


class ArtistToken:
    tag = "artist"
    field_defs = [
        FieldDef("fallback", "Fallback", "Unknown"),
        FieldDef("blank_on_paused", "Blank on paused media", "false", field_type="checkbox"),
    ]

    def resolve(self) -> str:
        blank_paused = self.fields["blank_on_paused"] == "true"
        if IS_WINDOWS:
            from services.tokens._media_win import _query_media_session
            info = _query_media_session()
            if info and info["artist"]:
                if blank_paused and info["status"] == "paused":
                    return ""
                return info["artist"]
            return self.fields["fallback"]
        from services.tokens._media_linux import playerctl
        try:
            result = playerctl("metadata", "--format", "{{status}}\n{{artist}}")
            if result.returncode == 0 and result.stdout.strip():
                status, _, artist = result.stdout.strip().partition("\n")
                if artist:
                    if blank_paused and status.lower() == "paused":
                        return ""
                    return artist
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return self.fields["fallback"]
