from services.text_processor import BLANKLINE_SENTINEL


class BlanklineToken:
    tag = "blankline"
    field_defs = []
    hint = "OpenChatbox automatically removes completely blank lines. This token forces a blank line and can be used on lines with other tokens to prevent removal if other token resolves blank."

    def resolve(self) -> str:
        return BLANKLINE_SENTINEL
