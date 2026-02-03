"""Shared fixtures for Bookmarker tests."""

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    """Redirect config dir to a temp directory for all tests."""
    config_dir = tmp_path / ".bookmarker"
    config_dir.mkdir()
    monkeypatch.setattr(
        "bookmarker.utils.config.get_config_dir",
        lambda: config_dir,
    )
    return config_dir


@pytest.fixture
def sample_bookmarks_data():
    """Return sample bookmark data for testing."""
    now = datetime.now().isoformat()
    return {
        "version": 1,
        "last_modified": now,
        "roots": {
            "bookmark_bar": {
                "id": str(uuid.uuid4()),
                "type": "folder",
                "title": "Bookmarks Bar",
                "url": "",
                "parent_id": None,
                "position": 0,
                "date_added": now,
                "date_modified": now,
                "preferred_browser": None,
                "source_browser": None,
                "source_id": None,
                "children": [
                    {
                        "id": str(uuid.uuid4()),
                        "type": "url",
                        "title": "Example",
                        "url": "https://example.com",
                        "parent_id": None,
                        "position": 0,
                        "date_added": now,
                        "date_modified": now,
                        "preferred_browser": None,
                        "source_browser": None,
                        "source_id": None,
                        "children": [],
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "type": "folder",
                        "title": "Dev",
                        "url": "",
                        "parent_id": None,
                        "position": 1,
                        "date_added": now,
                        "date_modified": now,
                        "preferred_browser": None,
                        "source_browser": None,
                        "source_id": None,
                        "children": [
                            {
                                "id": str(uuid.uuid4()),
                                "type": "url",
                                "title": "GitHub",
                                "url": "https://github.com",
                                "parent_id": None,
                                "position": 0,
                                "date_added": now,
                                "date_modified": now,
                                "preferred_browser": None,
                                "source_browser": None,
                                "source_id": None,
                                "children": [],
                            }
                        ],
                    },
                ],
            },
            "other": {
                "id": str(uuid.uuid4()),
                "type": "folder",
                "title": "Other Bookmarks",
                "url": "",
                "parent_id": None,
                "position": 0,
                "date_added": now,
                "date_modified": now,
                "preferred_browser": None,
                "source_browser": None,
                "source_id": None,
                "children": [],
            },
        },
    }


@pytest.fixture
def sample_chrome_data():
    """Return sample Chrome bookmark JSON data."""
    return {
        "checksum": "",
        "roots": {
            "bookmark_bar": {
                "children": [
                    {
                        "date_added": "13345678901234567",
                        "date_last_used": "0",
                        "guid": "00000000-0000-0000-0000-000000000001",
                        "id": "1",
                        "name": "Example",
                        "type": "url",
                        "url": "https://example.com",
                    },
                    {
                        "children": [
                            {
                                "date_added": "13345678901234567",
                                "date_last_used": "0",
                                "guid": "00000000-0000-0000-0000-000000000003",
                                "id": "3",
                                "name": "GitHub",
                                "type": "url",
                                "url": "https://github.com",
                            }
                        ],
                        "date_added": "13345678901234567",
                        "date_modified": "13345678901234567",
                        "guid": "00000000-0000-0000-0000-000000000002",
                        "id": "2",
                        "name": "Dev",
                        "type": "folder",
                    },
                ],
                "date_added": "13345678901234567",
                "date_modified": "13345678901234567",
                "guid": "00000000-0000-4000-0000-000000000000",
                "id": "0",
                "name": "Bookmarks bar",
                "type": "folder",
            },
            "other": {
                "children": [],
                "date_added": "13345678901234567",
                "date_modified": "0",
                "guid": "00000000-0000-4000-0000-000000000001",
                "id": "4",
                "name": "Other bookmarks",
                "type": "folder",
            },
            "synced": {
                "children": [],
                "date_added": "13345678901234567",
                "date_modified": "0",
                "guid": "00000000-0000-4000-0000-000000000002",
                "id": "5",
                "name": "Mobile bookmarks",
                "type": "folder",
            },
        },
        "version": 1,
    }
