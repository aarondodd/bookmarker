"""Configuration management for Bookmarker.

Stores configuration in ~/.bookmarker/config.toml
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older Python


def get_config_dir() -> Path:
    """Get the Bookmarker configuration directory."""
    config_dir = Path.home() / ".bookmarker"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    """Get the path to the config file."""
    return get_config_dir() / "config.toml"


def get_version_check_file() -> Path:
    """Get the path to the version check timestamp file."""
    return get_config_dir() / ".version_check"


def get_bookmarks_file() -> Path:
    """Get the path to the internal bookmarks store."""
    return get_config_dir() / "bookmarks.json"


def get_backups_dir() -> Path:
    """Get the path to the backups directory."""
    backups_dir = get_config_dir() / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    return backups_dir


def load_config() -> Dict[str, Any]:
    """Load configuration from the config file."""
    config_file = get_config_file()
    if not config_file.exists():
        return {}

    try:
        with open(config_file, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def save_config(config: Dict[str, Any]) -> Optional[str]:
    """Save configuration to the config file.

    Returns:
        Error message or None if successful.
    """
    config_file = get_config_file()

    try:
        lines = []
        for section, values in config.items():
            if isinstance(values, dict):
                lines.append(f"[{section}]")
                for key, value in values.items():
                    if isinstance(value, str):
                        lines.append(f'{key} = "{value}"')
                    elif isinstance(value, bool):
                        lines.append(f"{key} = {str(value).lower()}")
                    else:
                        lines.append(f"{key} = {value}")
                lines.append("")
            else:
                if isinstance(values, str):
                    lines.append(f'{section} = "{values}"')
                elif isinstance(values, bool):
                    lines.append(f"{section} = {str(values).lower()}")
                else:
                    lines.append(f"{section} = {values}")

        with open(config_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return None
    except Exception as e:
        return f"Error saving config: {e}"


def get_ui_config() -> Dict[str, Any]:
    """Get UI configuration settings."""
    config = load_config()
    return config.get("ui", {})


def set_ui_config(settings: Dict[str, Any]) -> Optional[str]:
    """Set UI configuration settings."""
    config = load_config()
    config["ui"] = settings
    return save_config(config)


def get_sync_config() -> Dict[str, Any]:
    """Get sync configuration settings."""
    config = load_config()
    return config.get("sync", {})


def set_sync_config(settings: Dict[str, Any]) -> Optional[str]:
    """Set sync configuration settings."""
    config = load_config()
    config["sync"] = settings
    return save_config(config)


def get_last_version_check() -> Optional[datetime]:
    """Get the timestamp of the last version check."""
    check_file = get_version_check_file()
    if not check_file.exists():
        return None

    try:
        with open(check_file, "r", encoding="utf-8") as f:
            timestamp_str = f.read().strip()
            return datetime.fromisoformat(timestamp_str)
    except Exception:
        return None


def record_version_check() -> None:
    """Record the current time as the last version check time."""
    check_file = get_version_check_file()
    try:
        with open(check_file, "w", encoding="utf-8") as f:
            f.write(datetime.now().isoformat())
    except Exception:
        pass


def create_default_config() -> None:
    """Create a default configuration file if it doesn't exist."""
    config_file = get_config_file()
    if config_file.exists():
        return

    default_config = {
        "ui": {
            "dark_mode": False,
        },
        "sync": {
            "debug_mode": False,
        },
    }
    save_config(default_config)
