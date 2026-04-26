import os
import sys
import logging
import tomllib
import tomli_w
from pathlib import Path

logger = logging.getLogger(__name__)


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

DEFAULTS = {
    "osc": {
        "ip": "127.0.0.1",
        "port": 9000
    },
    "chats": ["╔════ஓ๑♡๑ஓ════╗\n<nowplaying>\n<song_progress>\n<song_progress_bar>\n╚════ஓ๑♡๑ஓ════╝", "┍━━━━━»•» 🌺 «•«━┑\n<weather>\n┕━»•» 🌺 «•«━━━━━┙", "═✿══╡°˖✧✿✧˖°╞══✿═\nCPU: <cpu> <cpu_temp>\nGPU: <gpu> <gpu_temp>\nRAM: <ramgb>\n═✿══╡°˖✧✿✧˖°╞══✿═"],
    "tokens": {},
    "vrchat": {
        "auth_cookie": "",
        "two_factor_cookie": "",
    },
}

def load_config():
    if CONFIG_PATH.exists():
        logger.info("Loaded config from %s", CONFIG_PATH)
        with open(CONFIG_PATH, "rb") as f:
            user_config = tomllib.load(f)
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

def _merge(defaults, overrides):
    result = defaults.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result