"""Tests for OS-appropriate profile directory resolution."""

from pathlib import Path

from bookmarker.utils import config


def test_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("BOOKMARKER_DATA_DIR", str(tmp_path / "custom"))
    assert config._standard_config_dir() == tmp_path / "custom"


def test_windows_uses_appdata(monkeypatch):
    monkeypatch.delenv("BOOKMARKER_DATA_DIR", raising=False)
    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\x\AppData\Roaming")
    p = config._standard_config_dir()
    assert p.name == "Bookmarker"
    assert "Roaming" in str(p)


def test_macos_uses_application_support(monkeypatch):
    monkeypatch.delenv("BOOKMARKER_DATA_DIR", raising=False)
    monkeypatch.setattr(config.sys, "platform", "darwin")
    assert config._standard_config_dir() == (
        Path.home() / "Library" / "Application Support" / "Bookmarker"
    )


def test_linux_respects_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("BOOKMARKER_DATA_DIR", raising=False)
    monkeypatch.setattr(config.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert config._standard_config_dir() == tmp_path / "cfg" / "bookmarker"


def test_linux_default_config_dir(monkeypatch):
    monkeypatch.delenv("BOOKMARKER_DATA_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(config.sys, "platform", "linux")
    assert config._standard_config_dir() == Path.home() / ".config" / "bookmarker"


def test_no_tilde_bookmarker_default(monkeypatch):
    """The legacy ~/.bookmarker must no longer be the default anywhere."""
    monkeypatch.delenv("BOOKMARKER_DATA_DIR", raising=False)
    for plat in ("win32", "darwin", "linux"):
        monkeypatch.setattr(config.sys, "platform", plat)
        assert config._standard_config_dir() != Path.home() / ".bookmarker"


def test_migration_moves_legacy_profile(monkeypatch, tmp_path):
    """A legacy ~/.bookmarker profile migrates into the standard location once."""
    home = tmp_path / "home"
    home.mkdir()
    legacy = home / ".bookmarker"
    legacy.mkdir()
    (legacy / "bookmarks.json").write_text('{"roots": {}}')
    target = tmp_path / "profile" / "bookmarker"

    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: home))
    config._migrate_legacy_profile(target)

    assert (target / "bookmarks.json").exists()
    assert not legacy.exists()  # moved, not copied


def test_migration_skips_when_target_exists(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    legacy = home / ".bookmarker"
    legacy.mkdir()
    (legacy / "old.json").write_text("{}")
    target = tmp_path / "profile" / "bookmarker"
    target.mkdir(parents=True)

    monkeypatch.setattr(config.Path, "home", classmethod(lambda cls: home))
    config._migrate_legacy_profile(target)

    # Target already existed -> no migration; legacy left untouched.
    assert legacy.exists()
    assert not (target / "old.json").exists()
