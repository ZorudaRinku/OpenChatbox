import os
import tomllib
import tomli_w
import pytest
from unittest.mock import patch
from config import (
    load_config,
    save_config,
    backup_config,
    list_backups,
    quarantine_corrupt_config,
    restore_backup,
    ConfigError,
    _merge,
    DEFAULTS,
)


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


@pytest.fixture
def backup_env(tmp_path):
    config_file = tmp_path / "config.toml"
    backup_dir = tmp_path / "Backups"
    with patch("config.CONFIG_DIR", tmp_path), \
         patch("config.CONFIG_PATH", config_file), \
         patch("config.BACKUP_DIR", backup_dir):
        yield config_file, backup_dir


class TestBackupConfig:
    def test_creates_backup(self, backup_env):
        config_file, backup_dir = backup_env
        config_file.write_text('chats = ["hi"]\n')

        dest = backup_config()
        assert dest is not None
        assert dest.parent == backup_dir
        assert dest.name.startswith("config-")
        assert dest.read_text() == 'chats = ["hi"]\n'

    def test_no_config_no_backup(self, backup_env):
        assert backup_config() is None

    def test_skips_when_identical_to_last_backup(self, backup_env):
        config_file, backup_dir = backup_env
        config_file.write_text('chats = ["hi"]\n')

        assert backup_config() is not None
        assert backup_config() is None
        assert len(list(backup_dir.glob("config-*.toml"))) == 1

    def test_skips_when_identical_to_older_backup(self, backup_env):
        config_file, backup_dir = backup_env
        config_file.write_text('chats = ["one"]\n')
        first = backup_config()
        os.utime(first, (1, 1))
        config_file.write_text('chats = ["two"]\n')
        second = backup_config()
        os.utime(second, (2, 2))

        # Revert to the older backup's content: should match it and skip
        config_file.write_text('chats = ["one"]\n')
        assert backup_config() is None
        assert len(list(backup_dir.glob("config-*.toml"))) == 2

    def test_backs_up_again_when_changed(self, backup_env):
        config_file, backup_dir = backup_env
        config_file.write_text('chats = ["one"]\n')
        first = backup_config()
        config_file.write_text('chats = ["two"]\n')
        second = backup_config()

        assert first != second
        assert len(list(backup_dir.glob("config-*.toml"))) == 2

    def test_prunes_to_ten(self, backup_env):
        config_file, backup_dir = backup_env
        for i in range(13):
            config_file.write_text(f'chats = ["msg {i}"]\n')
            dest = backup_config()
            # Force distinct mtimes so prune order is deterministic
            os.utime(dest, (i, i))

        remaining = list(backup_dir.glob("config-*.toml"))
        assert len(remaining) == 10
        newest = list_backups()[0]
        assert newest.read_text() == 'chats = ["msg 12"]\n'

    def test_list_backups_newest_first(self, backup_env):
        config_file, _ = backup_env
        config_file.write_text('chats = ["a"]\n')
        first = backup_config()
        os.utime(first, (1, 1))
        config_file.write_text('chats = ["b"]\n')
        second = backup_config()
        os.utime(second, (2, 2))

        assert list_backups() == [second, first]


class TestCorruptConfig:
    def test_load_raises_config_error(self, backup_env):
        config_file, _ = backup_env
        config_file.write_bytes(b"\x00" * 64)

        with pytest.raises(ConfigError):
            load_config()

    def test_quarantine_moves_file(self, backup_env):
        config_file, backup_dir = backup_env
        config_file.write_bytes(b"\x00garbage")

        dest = quarantine_corrupt_config()
        assert not config_file.exists()
        assert dest.parent == backup_dir
        assert dest.name.startswith("corrupted-")
        assert dest.read_bytes() == b"\x00garbage"

    def test_quarantine_without_config(self, backup_env):
        assert quarantine_corrupt_config() is None

    def test_quarantined_files_not_listed_as_backups(self, backup_env):
        config_file, _ = backup_env
        config_file.write_bytes(b"\x00garbage")
        quarantine_corrupt_config()

        assert list_backups() == []

    def test_restore_backup(self, backup_env):
        config_file, backup_dir = backup_env
        backup_dir.mkdir()
        backup = backup_dir / "config-2026-01-01_00-00-00.toml"
        backup.write_text('chats = ["restored"]\n')

        restore_backup(backup)
        assert config_file.read_text() == 'chats = ["restored"]\n'
        assert load_config()["chats"] == ["restored"]
