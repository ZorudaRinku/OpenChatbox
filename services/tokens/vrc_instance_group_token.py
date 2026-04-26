from __future__ import annotations

from services.text_processor import FieldDef
from services import vrchat_service
from services.vrchat_service import VRC_HINT


class VrcInstanceGroupToken:
    tag = "vrc_instance_group"
    field_defs = [
        FieldDef("_account", "Account", "", field_type="vrchat_account"),
        FieldDef("show", "Show", "Name", field_type="dropdown",
                 options=["Name", "Short Code"]),
        FieldDef("fallback", "Fallback", "N/A"),
    ]
    hint = VRC_HINT

    def __init__(self):
        self._svc = vrchat_service.get_service()

    def resolve(self) -> str:
        group = self._svc.get_group()
        if not group:
            return self.fields["fallback"]
        if self.fields.get("show") == "Short Code":
            value = group.get("shortCode") or ""
        else:
            value = group.get("name") or ""
        value = value.strip()
        return value or self.fields["fallback"]
