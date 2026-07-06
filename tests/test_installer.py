"""Tests for extension extraction + native-host registration."""

import json
import sys

import pytest

from bookmarker.automation import installer


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect manifest writes away from the real ~/.config."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(installer, "_home", lambda: home)
    return home


def test_extension_id_matches_manifest_key():
    """The EXTENSION_ID constant must match the id derived from the bundled
    manifest's key -- a mismatch would silently break host<->extension auth."""
    source = installer._bundled_extension_source()
    manifest = json.loads((source / "manifest.json").read_text())
    derived = installer._derive_extension_id_from_key(manifest["key"])
    assert derived == installer.EXTENSION_ID


def test_extract_extension_copies_and_validates(isolate_config):
    dest = installer.extract_extension()
    assert (dest / "manifest.json").exists()
    assert (dest / "background.js").exists()
    assert installer.installed_extension_version() == installer.bundled_extension_version()


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX manifest paths")
def test_write_manifest_posix(isolate_config, fake_home):
    exe, args = installer.default_host_command()
    written = installer.write_native_host_manifest(host_executable=exe, host_args=args)
    # One manifest per Chromium-family browser dir.
    assert len(written) == 3
    for path in written:
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["name"] == installer.NATIVE_HOST_NAME
        assert data["allowed_origins"] == [
            f"chrome-extension://{installer.EXTENSION_ID}/"
        ]
        assert data["type"] == "stdio"


def test_install_uninstall_state(isolate_config, fake_home):
    state = installer.install()
    assert state["extension_extracted"] is True
    assert state["native_manifest_written"] is True
    assert installer.is_fully_installed() is True

    installer.uninstall()
    state2 = installer.installation_state()
    # Extension files are kept by default; native manifests are removed.
    assert state2["extension_extracted"] is True
    assert state2["native_manifest_written"] is False


def test_default_host_command_from_source():
    exe, args = installer.default_host_command()
    assert exe  # the interpreter
    assert args[-1] == "--native-host"
