from datetime import datetime
from services.text_processor import FieldDef


class TimeToken:
    tag = "time"
    field_defs = [FieldDef("format", "Format", "%I:%M %p")]

    def resolve(self) -> str:
        return datetime.now().strftime(self.fields["format"]).lstrip("0")
