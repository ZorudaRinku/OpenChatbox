from __future__ import annotations

from services.text_processor import FieldDef
from services import heartrate_service


class HeartrateEmoteToken:
    """Shows different emotes based on heart rate ranges."""
    tag = "heartrate_emote"
    hint = "Emote changes with heart rate (uses <heartrate> token device) - ≤BPM = Emote"
    field_defs = [
        FieldDef("emote_5", "Emote (above)", "\U0001f525 (⸝⸝ ♡﹏♡⸝⸝)"),
        FieldDef("threshold_4", "BPM", "120", field_type="spinbox", group=4),
        FieldDef("emote_4", "Emote", "\U0001f9e1 (˶˃ ᵕ ˂˶)", group=4),
        FieldDef("threshold_3", "BPM", "100", field_type="spinbox", group=3),
        FieldDef("emote_3", "Emote", "\U0001f49b (•﹏•;)", group=3),
        FieldDef("threshold_2", "BPM", "80", field_type="spinbox", group=2),
        FieldDef("emote_2", "Emote", "\U0001f49a (ㅇㅅㅇ)", group=2),
        FieldDef("threshold_1", "BPM", "60", field_type="spinbox", group=1),
        FieldDef("emote_1", "Emote", "\U0001f4a4 (=____=)", group=1),
        FieldDef("fallback", "Fallback", "\U0001f480 (╥﹏╥)"),
    ]

    def resolve(self) -> str:
        bpm = heartrate_service.get_active_bpm()
        if bpm is None:
            return self.fields["fallback"]
        try:
            thresholds = [
                (int(self.fields["threshold_1"]), self.fields["emote_1"]),
                (int(self.fields["threshold_2"]), self.fields["emote_2"]),
                (int(self.fields["threshold_3"]), self.fields["emote_3"]),
                (int(self.fields["threshold_4"]), self.fields["emote_4"]),
            ]
        except (ValueError, KeyError):
            return self.fields["fallback"]
        for threshold, emote in thresholds:
            if bpm <= threshold:
                return emote
        return self.fields["emote_5"]
