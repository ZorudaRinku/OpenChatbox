from datetime import datetime
from services.text_processor import FieldDef


class DateToken:
    tag = "date"
    field_defs = [FieldDef("format", "Format", "%m/%d/%Y")]

    def resolve(self) -> str:
        return datetime.now().strftime(self.fields["format"])
