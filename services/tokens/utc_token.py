from datetime import datetime, timezone
from services.text_processor import FieldDef


class UtcToken:
    tag = "utc"
    field_defs = [FieldDef("format", "Format", "%H:%M UTC")]

    def resolve(self) -> str:
        return datetime.now(timezone.utc).strftime(self.fields["format"])
