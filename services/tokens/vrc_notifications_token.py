from __future__ import annotations

from services.text_processor import FieldDef
from services import vrchat_service
from services.vrchat_service import VRC_HINT


class VrcNotificationsToken:
    tag = "vrc_notifications"
    field_defs = [
        FieldDef("_account", "Account", "", field_type="vrchat_account"),
        FieldDef("suffix", "Suffix", " unread"),
        FieldDef("fallback", "Fallback", ""),
    ]
    hint = VRC_HINT

    def __init__(self):
        self._svc = vrchat_service.get_service()

    def resolve(self) -> str:
        if not self._svc.is_authenticated():
            return self.fields["fallback"]
        count = self._svc.get_notifications_count()
        if count == 0:
            return self.fields["fallback"]
        return f"{count}{self.fields['suffix']}"
