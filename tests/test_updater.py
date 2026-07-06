"""Tests for the GitHub-releases-based, platform-aware updater."""

from datetime import datetime, timedelta
from unittest.mock import patch

from bookmarker.utils.updater import (
    parse_version,
    is_newer_version,
    should_check_for_updates,
    check_for_updates,
    install_kind,
    current_bundle_dir,
    find_asset,
    launch_installer,
    prune_updates_cache,
    upgrade,
    cleanup_stale_bundle,
    WINDOWS_ASSET_PATTERN,
    LINUX_ASSET_PATTERN,
)


def _release(tag, *asset_names):
    """Build a GitHub-release dict with the given asset filenames."""
    return {
        "tag_name": tag,
        "assets": [
            {"name": n, "browser_download_url": f"https://example.com/{n}"}
            for n in asset_names
        ],
        "html_url": "",
        "body": "",
    }


class TestParseVersion:
    def test_simple(self):
        assert parse_version("1.2.3") == (1, 2, 3)

    def test_with_v_prefix(self):
        assert parse_version("v1.2.3") == (1, 2, 3)

    def test_two_parts(self):
        assert parse_version("1.0") == (1, 0)

    def test_prerelease_suffix_stripped(self):
        assert parse_version("0.1.4-dev") == (0, 1, 4)
        assert parse_version("0.1.4+build7") == (0, 1, 4)

    def test_empty(self):
        assert parse_version("") is None

    def test_invalid(self):
        assert parse_version("abc") is None


class TestIsNewerVersion:
    def test_newer(self):
        assert is_newer_version("2.0.0", "1.0.0") is True

    def test_same(self):
        assert is_newer_version("1.0.0", "1.0.0") is False

    def test_older(self):
        assert is_newer_version("0.9.0", "1.0.0") is False

    def test_patch_newer(self):
        assert is_newer_version("1.0.1", "1.0.0") is True

    def test_with_v_prefix(self):
        assert is_newer_version("v2.0.0", "v1.0.0") is True

    def test_invalid_operand(self):
        assert is_newer_version("", "1.0.0") is False
        assert is_newer_version("2.0.0", "") is False


class TestShouldCheckForUpdates:
    def test_no_previous_check(self, isolate_config):
        assert should_check_for_updates() is True

    def test_recent_check(self, isolate_config):
        from bookmarker.utils.config import record_version_check

        record_version_check()
        assert should_check_for_updates() is False

    def test_old_check(self, isolate_config):
        from bookmarker.utils.config import get_version_check_file

        get_version_check_file().write_text(
            (datetime.now() - timedelta(days=8)).isoformat()
        )
        assert should_check_for_updates() is True


class TestCheckForUpdates:
    def test_no_update_available(self, isolate_config):
        with patch(
            "bookmarker.utils.updater.get_latest_release",
            return_value=_release("0.0.1"),
        ):
            assert check_for_updates() is None

    def test_update_available(self, isolate_config):
        with patch(
            "bookmarker.utils.updater.get_latest_release",
            return_value=_release("99.9.9"),
        ):
            result = check_for_updates()
        assert result is not None
        assert result[1] == "99.9.9"

    def test_api_failure(self, isolate_config):
        with patch("bookmarker.utils.updater.get_latest_release", return_value=None):
            assert check_for_updates() is None


class TestInstallKind:
    def test_source_when_not_frozen(self):
        with patch("bookmarker.utils.updater.is_frozen", return_value=False):
            assert install_kind() == "source"

    def test_windows_when_frozen(self):
        with patch("bookmarker.utils.updater.is_frozen", return_value=True), patch(
            "bookmarker.utils.updater.sys"
        ) as mock_sys:
            mock_sys.platform = "win32"
            assert install_kind() == "windows-installer"

    def test_linux_when_frozen(self):
        with patch("bookmarker.utils.updater.is_frozen", return_value=True), patch(
            "bookmarker.utils.updater.sys"
        ) as mock_sys:
            mock_sys.platform = "linux"
            assert install_kind() == "linux-tarball"

    def test_unknown_when_frozen_on_mac(self):
        with patch("bookmarker.utils.updater.is_frozen", return_value=True), patch(
            "bookmarker.utils.updater.sys"
        ) as mock_sys:
            mock_sys.platform = "darwin"
            assert install_kind() == "unknown"

    def test_current_bundle_dir_none_when_not_frozen(self):
        with patch("bookmarker.utils.updater.is_frozen", return_value=False):
            assert current_bundle_dir() is None


class TestAssetPatterns:
    def test_windows_match(self):
        m = WINDOWS_ASSET_PATTERN.match("bookmarker-setup-0.1.4.exe")
        assert m and m.group("version") == "0.1.4"

    def test_windows_reject(self):
        assert WINDOWS_ASSET_PATTERN.match("bookmarker-0.1.4.exe") is None
        assert WINDOWS_ASSET_PATTERN.match("bookmarker-setup-0.1.4.tar.gz") is None

    def test_linux_match(self):
        m = LINUX_ASSET_PATTERN.match("bookmarker-linux-x86_64-0.1.4.tar.gz")
        assert m and m.group("version") == "0.1.4"

    def test_linux_reject(self):
        assert LINUX_ASSET_PATTERN.match("bookmarker-linux-0.1.4.tar.gz") is None
        assert LINUX_ASSET_PATTERN.match("bookmarker-setup-0.1.4.exe") is None

    def test_find_asset_returns_version_and_url(self):
        rel = _release("0.1.4", "bookmarker-setup-0.1.4.exe")
        found = find_asset(rel, WINDOWS_ASSET_PATTERN)
        assert found == ("0.1.4", "https://example.com/bookmarker-setup-0.1.4.exe")

    def test_find_asset_none_when_absent(self):
        rel = _release("0.1.4", "bookmarker-linux-x86_64-0.1.4.tar.gz")
        assert find_asset(rel, WINDOWS_ASSET_PATTERN) is None


class TestUpgradeBranchSelection:
    def test_source_advises_rebuild(self):
        with patch("bookmarker.utils.updater.install_kind", return_value="source"):
            ok, msg = upgrade()
        assert ok is False
        assert "running from source" in msg
        assert "build.sh" in msg

    def test_unknown_platform(self):
        with patch("bookmarker.utils.updater.install_kind", return_value="unknown"):
            ok, msg = upgrade()
        assert ok is False
        assert "Windows and Linux" in msg

    def test_already_latest(self):
        from bookmarker.version import __version__

        with patch(
            "bookmarker.utils.updater.install_kind", return_value="windows-installer"
        ), patch(
            "bookmarker.utils.updater.get_latest_release",
            return_value=_release(__version__),
        ):
            ok, msg = upgrade()
        assert ok is True
        assert "latest version" in msg

    def test_windows_dispatch_downloads_and_launches(self):
        rel = _release("99.9.9", "bookmarker-setup-99.9.9.exe")
        with patch(
            "bookmarker.utils.updater.install_kind", return_value="windows-installer"
        ), patch(
            "bookmarker.utils.updater.get_latest_release", return_value=rel
        ), patch(
            "bookmarker.utils.updater.download_release", return_value=True
        ), patch(
            "bookmarker.utils.updater.launch_installer",
            return_value=(True, "Installer launched"),
        ) as mock_launch:
            ok, msg = upgrade()
        assert ok is True
        assert mock_launch.called

    def test_windows_missing_asset(self):
        rel = _release("99.9.9", "bookmarker-linux-x86_64-99.9.9.tar.gz")
        with patch(
            "bookmarker.utils.updater.install_kind", return_value="windows-installer"
        ), patch("bookmarker.utils.updater.get_latest_release", return_value=rel):
            ok, msg = upgrade()
        assert ok is False
        assert "no Windows installer asset" in msg


class TestLaunchInstaller:
    def test_missing_file(self, tmp_path):
        ok, msg = launch_installer(tmp_path / "nope.exe")
        assert ok is False
        assert "not found" in msg

    def test_launches_existing(self, tmp_path):
        installer = tmp_path / "bookmarker-setup-1.0.0.exe"
        installer.write_text("stub")
        with patch("bookmarker.utils.updater.subprocess.Popen") as mock_popen:
            ok, msg = launch_installer(installer)
        assert ok is True
        assert mock_popen.called


class TestLinuxUpgradeSwap:
    def test_dir_swap_and_reexec(self, tmp_path):
        # Simulate an installed onedir bundle: <root>/bookmarker/bookmarker
        install_root = tmp_path / "opt"
        bundle_dir = install_root / "bookmarker"
        bundle_dir.mkdir(parents=True)
        (bundle_dir / "bookmarker").write_text("old-launcher")
        (bundle_dir / "old-file.so").write_text("old")

        rel = _release("99.9.9", "bookmarker-linux-x86_64-99.9.9.tar.gz")

        def fake_download(url, dest):
            # Write a tarball whose top-level dir is bookmarker/
            import tarfile

            newbundle = tmp_path / "stage" / "bookmarker"
            newbundle.mkdir(parents=True, exist_ok=True)
            (newbundle / "bookmarker").write_text("new-launcher")
            (newbundle / "new-file.so").write_text("new")
            with tarfile.open(dest, "w:gz") as tf:
                tf.add(newbundle, arcname="bookmarker")
            return True

        captured = {}

        def fake_execv(path, argv):
            captured["path"] = path
            captured["argv"] = argv
            raise SystemExit(0)  # execv would replace the process; stop here

        with patch(
            "bookmarker.utils.updater.install_kind", return_value="linux-tarball"
        ), patch(
            "bookmarker.utils.updater.get_latest_release", return_value=rel
        ), patch(
            "bookmarker.utils.updater.current_bundle_dir", return_value=bundle_dir
        ), patch(
            "bookmarker.utils.updater.download_release", side_effect=fake_download
        ), patch(
            "bookmarker.utils.updater.os.execv", side_effect=fake_execv
        ):
            try:
                upgrade()
            except SystemExit:
                pass

        # New launcher swapped in, old bundle set aside, execv aimed at the new one.
        assert (bundle_dir / "bookmarker").read_text() == "new-launcher"
        assert (bundle_dir / "new-file.so").exists()
        assert captured["path"].endswith("bookmarker")
        assert (install_root / "bookmarker.old").exists()

    def test_missing_asset(self, tmp_path):
        bundle_dir = tmp_path / "opt" / "bookmarker"
        bundle_dir.mkdir(parents=True)
        rel = _release("99.9.9", "bookmarker-setup-99.9.9.exe")
        with patch(
            "bookmarker.utils.updater.install_kind", return_value="linux-tarball"
        ), patch(
            "bookmarker.utils.updater.get_latest_release", return_value=rel
        ), patch(
            "bookmarker.utils.updater.current_bundle_dir", return_value=bundle_dir
        ):
            ok, msg = upgrade()
        assert ok is False
        assert "no Linux asset" in msg


class TestPruneUpdatesCache:
    def test_keeps_newest(self, isolate_config):
        import os
        from bookmarker.utils.updater import updates_dir

        d = updates_dir()
        names = [
            "bookmarker-setup-0.1.0.exe",
            "bookmarker-setup-0.1.1.exe",
            "bookmarker-linux-x86_64-0.1.2.tar.gz",
        ]
        for i, n in enumerate(names):
            p = d / n
            p.write_text("x")
            # Stagger mtimes so ordering is deterministic.
            os.utime(p, (1000 + i, 1000 + i))
        deleted = prune_updates_cache(keep_newest=1)
        assert len(deleted) == 2
        remaining = list(d.glob("bookmarker-*"))
        assert len(remaining) == 1
        assert remaining[0].name == "bookmarker-linux-x86_64-0.1.2.tar.gz"

    def test_ignores_unrelated_files(self, isolate_config):
        from bookmarker.utils.updater import updates_dir

        d = updates_dir()
        (d / "notes.txt").write_text("keep me")
        deleted = prune_updates_cache(keep_newest=0)
        assert deleted == []
        assert (d / "notes.txt").exists()


class TestCleanupStaleBundle:
    def test_noop_when_source(self):
        with patch("bookmarker.utils.updater.install_kind", return_value="source"):
            cleanup_stale_bundle()  # must not raise

    def test_removes_old_dir(self, tmp_path):
        bundle_dir = tmp_path / "bookmarker"
        bundle_dir.mkdir()
        old = tmp_path / "bookmarker.old"
        old.mkdir()
        (old / "stale").write_text("x")
        with patch(
            "bookmarker.utils.updater.install_kind", return_value="linux-tarball"
        ), patch(
            "bookmarker.utils.updater.current_bundle_dir", return_value=bundle_dir
        ):
            cleanup_stale_bundle()
        assert not old.exists()
