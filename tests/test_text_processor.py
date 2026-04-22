from services.text_processor import TextProcessor, FieldDef, init_fields


class SimpleToken:
    tag = "greet"
    field_defs = [FieldDef("name", "Name", "World")]
    fields: dict[str, str]

    def resolve(self) -> str:
        return f"Hello, {self.fields['name']}!"


class StaticToken:
    tag = "static"
    field_defs = []
    fields: dict[str, str]

    def resolve(self) -> str:
        return "STATIC"


class TestInitFields:
    def test_defaults_applied(self):
        token = SimpleToken()
        init_fields(token)
        assert token.fields == {"name": "World"}

    def test_overrides_applied(self):
        token = SimpleToken()
        init_fields(token, {"name": "Alice"})
        assert token.fields == {"name": "Alice"}

    def test_unknown_override_ignored(self):
        token = SimpleToken()
        init_fields(token, {"name": "Bob", "bogus": "ignored"})
        assert token.fields == {"name": "Bob"}
        assert "bogus" not in token.fields

    def test_override_cast_to_str(self):
        token = SimpleToken()
        init_fields(token, {"name": 42})
        assert token.fields["name"] == "42"

    def test_no_overrides(self):
        token = SimpleToken()
        init_fields(token, None)
        assert token.fields == {"name": "World"}

    def test_empty_field_defs(self):
        token = StaticToken()
        init_fields(token)
        assert token.fields == {}


class TestTextProcessor:
    def test_register_and_process(self):
        tp = TextProcessor()
        token = SimpleToken()
        init_fields(token)
        tp.register(token)
        assert tp.process("Say <greet>") == "Say Hello, World!"

    def test_no_match_passthrough(self):
        tp = TextProcessor()
        assert tp.process("no tokens here") == "no tokens here"

    def test_multiple_tokens(self):
        tp = TextProcessor()
        t1 = SimpleToken()
        init_fields(t1)
        t2 = StaticToken()
        init_fields(t2)
        tp.register(t1)
        tp.register(t2)
        assert tp.process("<greet> <static>") == "Hello, World! STATIC"

    def test_repeated_placeholder(self):
        tp = TextProcessor()
        token = StaticToken()
        init_fields(token)
        tp.register(token)
        assert tp.process("<static>/<static>") == "STATIC/STATIC"

    def test_partial_tag_not_replaced(self):
        tp = TextProcessor()
        token = StaticToken()
        init_fields(token)
        tp.register(token)
        assert tp.process("static") == "static"
        assert tp.process("<stati>") == "<stati>"

    def test_empty_string(self):
        tp = TextProcessor()
        assert tp.process("") == ""
