from __future__ import annotations

import time

from services.text_processor import FieldDef
from services import vrchat_service
from services.vrchat_service import VRC_HINT


class VrcSessionLengthToken:
    """Time since VRChat last login"""

    tag = "vrc_session_length"
    field_defs = [
        FieldDef("_account", "Account", "", field_type="vrchat_account"),
        FieldDef("fallback", "Fallback", "N/A"),
    ]
    hint = VRC_HINT

    def __init__(self):
        self._svc = vrchat_service.get_service()

    def resolve(self) -> str:
        last_login = self._svc.get_last_login_epoch()
        if last_login is None:
            return self.fields["fallback"]
        elapsed = int(time.time() - last_login)
        if elapsed < 0:
            elapsed = 0
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
