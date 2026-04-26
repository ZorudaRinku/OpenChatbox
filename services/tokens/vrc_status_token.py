from __future__ import annotations

from services.text_processor import FieldDef
from services import vrchat_service
from services.vrchat_service import VRC_HINT


class VrcStatusToken:
    """User-set VRChat status (active / join me / ask me / busy / offline)"""

    tag = "vrc_status"
    field_defs = [
        FieldDef("_account", "Account", "", field_type="vrchat_account"),
        FieldDef("fallback", "Fallback", "offline"),
    ]
    hint = VRC_HINT

    def __init__(self):
        self._svc = vrchat_service.get_service()

    def resolve(self) -> str:
        user = self._svc.get_user()
        if not user:
            return self.fields["fallback"]
        state = user.get("state", "")
        status = user.get("status", "")
        if state in ("online", "active") and status:
            return status.title()
        return self.fields["fallback"]
