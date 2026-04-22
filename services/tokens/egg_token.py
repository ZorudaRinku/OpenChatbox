class EggToken:
    tag = "egg"
    field_defs = []
    hint = "Only works at end of message"

    def resolve(self) -> str:
        return "\u0003\u001f"
