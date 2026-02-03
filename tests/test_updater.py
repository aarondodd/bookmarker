"""Tests for GitHub releases updater."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from bookmarker.utils.updater import (
    parse_version,
    is_newer_version,
    should_check_for_updates,
    check_for_updates,
    find_build_script,
    extract_archive,
    GITHUB_REPO,
)


class TestParseVersion:
    def test_simple(self):
        assert parse_version("1.2.3") == (1, 2, 3)

    def test_with_v_prefix(self):
        assert parse_version("v1.2.3") == (1, 2, 3)

    def test_two_parts(self):
        assert parse_version("1.0") == (1, 0)

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

    def test_minor_newer(self):
        assert is_newer_version("1.1.0", "1.0.0") is True

    def test_patch_newer(self):
        assert is_newer_version("1.0.1", "1.0.0") is True

    def test_with_v_prefix(self):
        assert is_newer_version("v2.0.0", "v1.0.0") is True

    def test_invalid_remote(self):
        assert is_newer_version("", "1.0.0") is False

    def test_invalid_local(self):
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
        check_file = get_version_check_file()
        old_time = datetime.now() - timedelta(days=8)
        check_file.write_text(old_time.isoformat())
        assert should_check_for_updates() is True


class TestCheckForUpdates:
    def test_no_update_available(self, isolate_config):
        mock_release = {"tag_name": "0.1.0", "zip_url": "https://example.com/zip"}
        with patch("bookmarker.utils.updater.get_latest_release", return_value=mock_release):
            result = check_for_updates()
        assert result is None

    def test_update_available(self, isolate_config):
        mock_release = {"tag_name": "9.9.9", "zip_url": "https://example.com/zip"}
        with patch("bookmarker.utils.updater.get_latest_release", return_value=mock_release):
            result = check_for_updates()
        assert result is not None
        local, remote = result
        assert remote == "9.9.9"

    def test_api_failure(self, isolate_config):
        with patch("bookmarker.utils.updater.get_latest_release", return_value=None):
            result = check_for_updates()
        assert result is None


class TestFindBuildScript:
    def test_direct_path(self, tmp_path):
        script = tmp_path / "build.sh"
        script.touch()
        result = find_build_script(str(tmp_path))
        assert result == str(script)

    def test_nested(self, tmp_path):
        nested = tmp_path / "subdir"
        nested.mkdir()
        script = nested / "build.sh"
        script.touch()
        with patch("bookmarker.utils.updater.platform.system", return_value="Linux"):
            result = find_build_script(str(tmp_path))
        assert result == str(script)

    def test_not_found(self, tmp_path):
        result = find_build_script(str(tmp_path))
        assert result is None


class TestExtractArchive:
    def test_extract(self, tmp_path):
        import zipfile

        # Create a test zip
        zip_path = tmp_path / "test.zip"
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("hello")

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(src_dir / "file.txt", "source/file.txt")

        result = extract_archive(str(zip_path), str(extract_dir))
        assert result is not None

    def test_bad_zip(self, tmp_path):
        bad_zip = tmp_path / "bad.zip"
        bad_zip.write_text("not a zip")
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        result = extract_archive(str(bad_zip), str(extract_dir))
        assert result is None
