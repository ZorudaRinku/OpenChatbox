from datetime import datetime
from services.text_processor import FieldDef


class TimezoneToken:
    tag = "timezone"
    field_defs = [FieldDef("format", "Format", "%Z")]

    def resolve(self) -> str:
        return datetime.now().astimezone().strftime(self.fields["format"])
