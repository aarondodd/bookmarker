"""Tests for the native-messaging wire framing."""

import io
import struct

import pytest

from bookmarker.automation.protocol import (
    ProtocolError,
    encode_message,
    read_message,
    write_message,
)


def test_round_trip():
    payload = {"type": "ping", "request_id": "abc", "nested": {"a": [1, 2, 3]}}
    stream = io.BytesIO(encode_message(payload))
    assert read_message(stream) == payload


def test_write_then_read():
    payload = {"type": "tree", "nodes": []}
    buf = io.BytesIO()
    write_message(buf, payload)
    buf.seek(0)
    assert read_message(buf) == payload


def test_clean_eof_returns_none():
    assert read_message(io.BytesIO(b"")) is None


def test_zero_length_is_empty_dict():
    assert read_message(io.BytesIO(struct.pack("<I", 0))) == {}


def test_short_read_raises():
    # Declares 100 bytes but supplies 3.
    data = struct.pack("<I", 100) + b"abc"
    with pytest.raises(ProtocolError):
        read_message(io.BytesIO(data))


def test_oversize_declared_length_raises():
    data = struct.pack("<I", 999_999_999) + b"x"
    with pytest.raises(ProtocolError):
        read_message(io.BytesIO(data))


def test_non_json_body_raises():
    body = b"not json"
    data = struct.pack("<I", len(body)) + body
    with pytest.raises(ProtocolError):
        read_message(io.BytesIO(data))


def test_non_object_json_raises():
    body = b"[1, 2, 3]"
    data = struct.pack("<I", len(body)) + body
    with pytest.raises(ProtocolError):
        read_message(io.BytesIO(data))
