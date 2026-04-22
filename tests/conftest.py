import pytest
from unittest.mock import MagicMock
from services.text_processor import TextProcessor, FieldDef, init_fields


class DummyToken:
    tag = "dummy"
    field_defs = [FieldDef("value", "Value", "hello")]
    fields: dict[str, str]

    def resolve(self) -> str:
        return self.fields["value"]


@pytest.fixture
def dummy_token():
    token = DummyToken()
    init_fields(token)
    return token


@pytest.fixture
def text_processor(dummy_token):
    tp = TextProcessor()
    tp.register(dummy_token)
    return tp


@pytest.fixture
def mock_osc_client():
    return MagicMock()


@pytest.fixture
def sample_config():
    return {
        "osc": {"ip": "127.0.0.1", "port": 9000},
        "chats": ["Hello world", "<time>"],
        "tokens": {},
    }
