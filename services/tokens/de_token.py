import os
from services.text_processor import FieldDef
from services.platform_info import IS_WINDOWS, IS_LINUX


class DeToken:
    tag = "de"
    field_defs = [FieldDef("fallback", "Fallback", "Unknown")]
    hint = "Desktop Enviornment"

    def resolve(self) -> str:
        if IS_WINDOWS:
            return "Windows"

        if not IS_LINUX:
            return self.fields["fallback"]

        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
        if desktop:
            return desktop

        session = os.environ.get("DESKTOP_SESSION", "")
        if session:
            return session

        return self.fields["fallback"]
