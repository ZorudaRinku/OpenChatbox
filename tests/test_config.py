import tomllib
import tomli_w
import pytest
from unittest.mock import patch
from config import load_config, save_config, _merge, DEFAULTS


class TestMerge:
    def test_flat_override(self):
        result = _merge({"a": 1, "b": 2}, {"b": 3})
        assert result == {"a": 1, "b": 3}

    def test_nested_override(self):
        defaults = {"osc": {"ip": "127.0.0.1", "port": 9000}}
        overrides = {"osc": {"port": 8000}}
        result = _merge(defaults, overrides)
        assert result == {"osc": {"ip": "127.0.0.1", "port": 8000}}

    def test_new_key_added(self):
        result = _merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_does_not_mutate_defaults(self):
        defaults = {"a": 1, "nested": {"x": 10}}
        _merge(defaults, {"a": 2, "nested": {"y": 20}})
        assert defaults == {"a": 1, "nested": {"x": 10}}

    def test_override_dict_with_scalar(self):
        result = _merge({"a": {"nested": True}}, {"a": 42})
        assert result == {"a": 42}

    def test_override_scalar_with_dict(self):
        result = _merge({"a": 42}, {"a": {"nested": True}})
        assert result == {"a": {"nested": True}}

    def test_empty_overrides(self):
        result = _merge({"a": 1}, {})
        assert result == {"a": 1}

    def test_deeply_nested(self):
        defaults = {"a": {"b": {"c": 1, "d": 2}}}
        overrides = {"a": {"b": {"c": 99}}}
        result = _merge(defaults, overrides)
        assert result == {"a": {"b": {"c": 99, "d": 2}}}


class TestLoadConfig:
    def test_loads_existing_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        data = {"osc": {"ip": "10.0.0.1", "port": 8000}, "chats": ["hi"]}
        with open(config_file, "wb") as f:
            tomli_w.dump(data, f)

        with patch("config.CONFIG_PATH", config_file):
            result = load_config()
        assert result["osc"]["ip"] == "10.0.0.1"
        assert result["osc"]["port"] == 8000
        assert result["chats"] == ["hi"]
        # Defaults merged in
        assert "tokens" in result

    def test_creates_default_when_missing(self, tmp_path):
        config_file = tmp_path / "config.toml"
        assert not config_file.exists()

        with patch("config.CONFIG_PATH", config_file):
            result = load_config()
        assert result["osc"] == DEFAULTS["osc"]
        assert result["chats"] == DEFAULTS["chats"]
        assert config_file.exists()

    def test_partial_config_gets_defaults(self, tmp_path):
        config_file = tmp_path / "config.toml"
        with open(config_file, "wb") as f:
            tomli_w.dump({"chats": ["test"]}, f)

        with patch("config.CONFIG_PATH", config_file):
            result = load_config()
        assert result["chats"] == ["test"]
        assert result["osc"] == DEFAULTS["osc"]


class TestSaveConfig:
    def test_save_and_reload(self, tmp_path):
        config_file = tmp_path / "config.toml"
        data = {"osc": {"ip": "1.2.3.4", "port": 1234}, "chats": ["saved"]}

        with patch("config.CONFIG_PATH", config_file):
            save_config(data)

        with open(config_file, "rb") as f:
            loaded = tomllib.load(f)
        assert loaded == data

    def test_atomic_write(self, tmp_path):
        """Temp file should not persist after successful rename."""
        config_file = tmp_path / "config.toml"
        with patch("config.CONFIG_PATH", config_file):
            save_config(DEFAULTS)
        assert not (tmp_path / "config.tmp").exists()
        assert config_file.exists()
