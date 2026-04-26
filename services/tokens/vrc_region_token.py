from __future__ import annotations

from services.text_processor import FieldDef
from services import vrchat_service
from services.vrchat_service import VRC_HINT


_REGION_LABELS = {
    "us": "US",
    "use": "USE",
    "usw": "USW",
    "usx": "USX",
    "eu": "EU",
    "jp": "JP",
}


class VrcRegionToken:
    """Region of the active VRChat instance (US / EU / JP / ...)"""
    
    tag = "vrc_region"
    field_defs = [
        FieldDef("_account", "Account", "", field_type="vrchat_account"),
        FieldDef("fallback", "Fallback", "N/A"),
    ]
    hint = VRC_HINT

    def __init__(self):
        self._svc = vrchat_service.get_service()

    def resolve(self) -> str:
        instance = self._svc.get_instance()
        if not instance:
            return self.fields["fallback"]
        region = (instance.get("region") or "").strip().lower()
        if not region:
            return self.fields["fallback"]
        return _REGION_LABELS.get(region, region.upper())
