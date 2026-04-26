from __future__ import annotations

from services.text_processor import FieldDef
from services import vrchat_service
from services.vrchat_service import VRC_HINT


class VrcWorldsHoppedToken:
    """Distinct worlds visited since OpenChatbox signed in."""

    tag = "vrc_worlds_hopped"
    field_defs = [
        FieldDef("_account", "Account", "", field_type="vrchat_account"),
        FieldDef("suffix", "Suffix", " worlds hopped"),
        FieldDef("fallback", "Fallback", "0 worlds"),
    ]
    hint = VRC_HINT

    def __init__(self):
        self._svc = vrchat_service.get_service()

    def resolve(self) -> str:
        if not self._svc.is_authenticated():
            return self.fields["fallback"]
        return f"{self._svc.get_worlds_hopped_count()}{self.fields['suffix']}"
