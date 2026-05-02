from __future__ import annotations

from services.text_processor import FieldDef
from services import vrchat_service
from services.vrchat_service import VRC_HINT


class VrcFriendsInInstanceToken:
    tag = "vrc_friends_in_instance"
    field_defs = [
        FieldDef("_account", "Account", "", field_type="vrchat_account"),
        FieldDef("suffix", "Suffix", " friends here"),
        FieldDef("fallback", "Fallback", "N/A"),
    ]
    hint = VRC_HINT

    def __init__(self):
        self._svc = vrchat_service.get_service()

    def resolve(self) -> str:
        if not self._svc.is_authenticated():
            return self.fields["fallback"]
        return f"{self._svc.get_friends_in_instance_count()}{self.fields['suffix']}"
