"""Tests for configuration management."""

from datetime import datetime, timedelta
from pathlib import Path

from bookmarker.utils.config import (
    get_config_dir,
    get_config_file,
    get_bookmarks_file,
    get_backups_dir,
    load_config,
    save_config,
    get_ui_config,
    set_ui_config,
    get_sync_config,
    set_sync_config,
    get_last_version_check,
    record_version_check,
    create_default_config,
)


class TestConfigPaths:
    def test_config_dir_exists(self, isolate_config):
        assert get_config_dir().exists()

    def test_config_file_path(self, isolate_config):
        assert get_config_file().name == "config.toml"

    def test_bookmarks_file_path(self, isolate_config):
        assert get_bookmarks_file().name == "bookmarks.json"

    def test_backups_dir_created(self, isolate_config):
        backups = get_backups_dir()
        assert backups.exists()
        assert backups.name == "backups"


class TestLoadSaveConfig:
    def test_load_empty_config(self, isolate_config):
        config = load_config()
        assert config == {}

    def test_save_and_load_roundtrip(self, isolate_config):
        config = {
            "ui": {"dark_mode": True},
            "sync": {"debug_mode": False},
        }
        result = save_config(config)
        assert result is None

        loaded = load_config()
        assert loaded["ui"]["dark_mode"] is True
        assert loaded["sync"]["debug_mode"] is False

    def test_save_string_values(self, isolate_config):
        config = {"ui": {"theme": "dark"}}
        save_config(config)
        loaded = load_config()
        assert loaded["ui"]["theme"] == "dark"

    def test_save_numeric_values(self, isolate_config):
        config = {"sync": {"interval": 60}}
        save_config(config)
        loaded = load_config()
        assert loaded["sync"]["interval"] == 60


class TestUIConfig:
    def test_get_default_ui_config(self, isolate_config):
        config = get_ui_config()
        assert config == {}

    def test_set_and_get_ui_config(self, isolate_config):
        set_ui_config({"dark_mode": True})
        config = get_ui_config()
        assert config["dark_mode"] is True


class TestSyncConfig:
    def test_get_default_sync_config(self, isolate_config):
        config = get_sync_config()
        assert config == {}

    def test_set_and_get_sync_config(self, isolate_config):
        set_sync_config({"debug_mode": True})
        config = get_sync_config()
        assert config["debug_mode"] is True


class TestVersionCheck:
    def test_no_previous_check(self, isolate_config):
        assert get_last_version_check() is None

    def test_record_and_retrieve(self, isolate_config):
        record_version_check()
        last_check = get_last_version_check()
        assert last_check is not None
        assert (datetime.now() - last_check) < timedelta(seconds=5)


class TestDefaultConfig:
    def test_creates_default(self, isolate_config):
        create_default_config()
        config = load_config()
        assert "ui" in config
        assert config["ui"]["dark_mode"] is False

    def test_does_not_overwrite(self, isolate_config):
        save_config({"ui": {"dark_mode": True}})
        create_default_config()
        config = load_config()
        assert config["ui"]["dark_mode"] is True
