from __future__ import annotations

from services.text_processor import FieldDef
from services import vrchat_service
from services.vrchat_service import VRC_HINT


class VrcFriendsTotalToken:
    tag = "vrc_friends_total"
    field_defs = [
        FieldDef("_account", "Account", "", field_type="vrchat_account"),
        FieldDef("suffix", "Suffix", " friends"),
        FieldDef("fallback", "Fallback", "N/A"),
    ]
    hint = VRC_HINT

    def __init__(self):
        self._svc = vrchat_service.get_service()

    def resolve(self) -> str:
        user = self._svc.get_user()
        if not user:
            return self.fields["fallback"]
        friends = user.get("friends") or []
        return f"{len(friends)}{self.fields['suffix']}"
