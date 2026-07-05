import os
import sys
import shutil
import logging
import tomllib
import tomli_w
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when config.toml exists but cannot be parsed."""


def _config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "OpenChatbox"


def _migrate_config_dir(new_dir: Path):
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    old_dir = base / "Chatbox"
    if old_dir.is_dir() and not new_dir.exists():
        old_dir.rename(new_dir)
        logger.info("Migrated config from %s to %s", old_dir, new_dir)


CONFIG_DIR = _config_dir()
_migrate_config_dir(CONFIG_DIR)
CONFIG_PATH = CONFIG_DIR / "config.toml"
BACKUP_DIR = CONFIG_DIR / "Backups"
MAX_BACKUPS = 10

DEFAULTS = {
    "osc": {
        "ip": "127.0.0.1",
        "port": 9000,
        "cycle_interval": 4,
        "update_interval": 2,
    },
    "chats": ["╔════ஓ๑♡๑ஓ════╗\n<nowplaying>\n<song_progress>\n<song_progress_bar>\n╚════ஓ๑♡๑ஓ════╝", "┍━━━━━»•» 🌺 «•«━┑\n<weather>\n┕━»•» 🌺 «•«━━━━━┙", "═✿══╡°˖✧✿✧˖°╞══✿═\nCPU: <cpu> <cpu_temp>\nGPU: <gpu> <gpu_temp>\nRAM: <ramgb>\n═✿══╡°˖✧✿✧˖°╞══✿═"],
    "tokens": {},
    "settings": {
        "preserve_blank_lines": False,
    },
    "vrchat": {
        "auth_cookie": "",
        "two_factor_cookie": "",
    },
}

def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "rb") as f:
                user_config = tomllib.load(f)
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
            logger.error("Failed to parse %s: %s", CONFIG_PATH, e)
            raise ConfigError(f"Could not read {CONFIG_PATH}: {e}") from e
        logger.info("Loaded config from %s", CONFIG_PATH)
        return _merge(DEFAULTS, user_config)
    else:
        logger.info("No config found, using defaults")
        save_config(DEFAULTS)
        return DEFAULTS.copy()

def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        tomli_w.dump(config, f)
    tmp.replace(CONFIG_PATH)

def list_backups():
    """Return backup files, newest first. Excludes quarantined corrupt copies."""
    if not BACKUP_DIR.is_dir():
        return []
    backups = BACKUP_DIR.glob("config-*.toml")
    return sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)

def backup_config():
    """Copy config.toml into Backups/ with a timestamp.

    Skipped when the current config is byte-identical to any existing backup.
    Keeps at most MAX_BACKUPS backups.
    """
    if not CONFIG_PATH.exists():
        return None
    try:
        data = CONFIG_PATH.read_bytes()
        for backup in list_backups():
            if backup.read_bytes() == data:
                logger.debug("Config matches existing backup %s, skipping", backup.name)
                return None
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dest = _timestamped_path("config")
        dest.write_bytes(data)
        _prune_backups("config-*.toml")
        logger.info("Backed up config to %s", dest)
        return dest
    except OSError as e:
        logger.error("Config backup failed: %s", e)
        return None

def quarantine_corrupt_config():
    """Move an unreadable config.toml into Backups/ as a corrupted copy."""
    if not CONFIG_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = _timestamped_path("corrupted")
    CONFIG_PATH.replace(dest)
    _prune_backups("corrupted-*.toml")
    logger.warning("Moved corrupt config to %s", dest)
    return dest

def restore_backup(backup_path):
    """Replace config.toml with the given backup file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(backup_path, CONFIG_PATH)
    logger.info("Restored config from %s", backup_path)

def _timestamped_path(prefix):
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dest = BACKUP_DIR / f"{prefix}-{stamp}.toml"
    counter = 1
    while dest.exists():
        dest = BACKUP_DIR / f"{prefix}-{stamp}-{counter}.toml"
        counter += 1
    return dest

def _prune_backups(pattern):
    files = sorted(BACKUP_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[MAX_BACKUPS:]:
        old.unlink(missing_ok=True)

def _merge(defaults, overrides):
    result = defaults.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result