from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass
class FieldDef:
    key: str
    label: str
    default: str
    field_type: str = "text"
    options: list[str] | None = None
    visible_when: dict[str, str] | None = None
    group: int | None = None
    hide_label: bool = False


class Token(Protocol):
    tag: str
    field_defs: list[FieldDef]
    fields: dict[str, str]
    def resolve(self) -> str: ...


def init_fields(token, overrides: dict[str, str] | None = None):
    token.fields = {fd.key: fd.default for fd in token.field_defs}
    if overrides:
        for key, value in overrides.items():
            if key in token.fields:
                token.fields[key] = str(value)


BLANKLINE_SENTINEL = "\x00BLANKLINE\x00"


class TextProcessor:
    def __init__(self):
        self.tokens: dict[str, Token] = {}

    def register(self, token: Token):
        self.tokens[token.tag] = token
        logger.debug("Registered token <%s>", token.tag)

    def process(self, text: str) -> str:
        for tag, token in self.tokens.items():
            placeholder = f"<{tag}>"
            if placeholder in text:
                try:
                    text = text.replace(placeholder, token.resolve())
                except Exception:
                    logger.exception("Token <%s> failed to resolve", tag)
                    text = text.replace(placeholder, "")
        # Remove completely blank lines, then restore <blankline> sentinels
        lines = text.split("\n")
        lines = [line for line in lines if line.strip() or BLANKLINE_SENTINEL in line]
        text = "\n".join(lines)
        text = text.replace(BLANKLINE_SENTINEL, "")
        return text
