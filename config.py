import json
import sys
from pathlib import Path

APP_NAME = "ScriptsArchitect"
CONFIG_DIR = Path.home() / f".{APP_NAME.lower()}"
SETTINGS_FILE = CONFIG_DIR / "settings.json"


def _default_manifest_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "Manifest"
    return Path.cwd() / "Manifest"


def load_settings() -> dict:
    settings = {
        "manifest_root": str(_default_manifest_root()),
        "environment_master_key": "",
    }

    if SETTINGS_FILE.exists():
        try:
            loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                settings.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass

    return settings


def save_settings(settings: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def get_manifest_root() -> Path:
    settings = load_settings()
    return Path(settings["manifest_root"]).expanduser()


def set_manifest_root(manifest_root: str | Path) -> Path:
    resolved_root = Path(manifest_root).expanduser()
    settings = load_settings()
    settings["manifest_root"] = str(resolved_root)
    save_settings(settings)
    return resolved_root


def get_environment_master_key() -> str:
    settings = load_settings()
    return str(settings.get("environment_master_key", ""))


def set_environment_master_key(master_key: str) -> None:
    settings = load_settings()
    settings["environment_master_key"] = str(master_key)
    save_settings(settings)
