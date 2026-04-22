import subprocess

from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS


class ArtistToken:
    tag = "artist"
    field_defs = [FieldDef("fallback", "Fallback", "Unknown")]

    def resolve(self) -> str:
        if IS_WINDOWS:
            from services.tokens._media_win import _query_media_session
            info = _query_media_session()
            if info and info["artist"]:
                return info["artist"]
            return self.fields["fallback"]
        from services.tokens._media_linux import playerctl
        try:
            result = playerctl("metadata", "artist")
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return self.fields["fallback"]
