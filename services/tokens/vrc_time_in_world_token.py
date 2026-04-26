from __future__ import annotations

import time

from services.text_processor import FieldDef
from services import vrchat_service
from services.vrchat_service import VRC_HINT


class VrcTimeInWorldToken:
    """Time elapsed since entering the current VRChat world"""

    tag = "vrc_time_in_world"
    field_defs = [
        FieldDef("_account", "Account", "", field_type="vrchat_account"),
        FieldDef("fallback", "Fallback", "N/A"),
    ]
    hint = VRC_HINT

    def __init__(self):
        self._svc = vrchat_service.get_service()

    def resolve(self) -> str:
        entered = self._svc.get_world_entered_at()
        if entered is None:
            return self.fields["fallback"]
        elapsed = max(0, int(time.monotonic() - entered))
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"
