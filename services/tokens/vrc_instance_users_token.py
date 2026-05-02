from __future__ import annotations

from services.text_processor import FieldDef
from services import vrchat_service
from services.vrchat_service import VRC_HINT


class VrcInstanceUsersToken:
    tag = "vrc_instance_users"
    field_defs = [
        FieldDef("_account", "Account", "", field_type="vrchat_account"),
        FieldDef("separator", "Separator", "/"),
        FieldDef("suffix", "Suffix", ""),
        FieldDef("fallback", "Fallback", "N/A"),
    ]
    hint = VRC_HINT

    def __init__(self):
        self._svc = vrchat_service.get_service()

    def resolve(self) -> str:
        instance = self._svc.get_instance()
        if not instance:
            return self.fields["fallback"]
        n = instance.get("n_users")
        cap = instance.get("capacity")
        if n is None or cap is None:
            return self.fields["fallback"]
        text = f"{n}{self.fields['separator']}{cap}{self.fields['suffix']}"
        queue = instance.get("queueSize") or 0
        if n >= cap and queue > 0:
            text = f"{text} ({queue})"
        return text
