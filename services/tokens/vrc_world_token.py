from __future__ import annotations

from services.text_processor import FieldDef
from services import vrchat_service
from services.vrchat_service import VRC_HINT


class VrcWorldToken:
    """Name of the world the signed-in user is currently in"""

    tag = "vrc_world"
    field_defs = [
        FieldDef("_account", "Account", "", field_type="vrchat_account"),
        FieldDef("fallback", "Fallback", "N/A"),
    ]
    hint = VRC_HINT

    def __init__(self):
        self._svc = vrchat_service.get_service()

    def resolve(self) -> str:
        world = self._svc.get_world()
        if not world:
            return self.fields["fallback"]
        name = (world.get("name") or "").strip()
        return name or self.fields["fallback"]
