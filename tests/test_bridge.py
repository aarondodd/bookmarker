"""Tests for the app-side loopback bridge, using an in-process TCP client that
speaks the framed protocol in place of the real Chrome native host."""

import json
import socket
import time

from bookmarker.automation import messages
from bookmarker.automation.bridge import Bridge
from bookmarker.automation.protocol import read_message, write_message


def _wait(predicate, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def _connect(port):
    sock = socket.create_connection(("127.0.0.1", port), timeout=2.0)
    return sock, sock.makefile("rwb")


def _handshake(stream, token, ext_id="ext123"):
    write_message(stream, {
        "type": messages.HANDSHAKE,
        "token": token,
        "host_version": "1",
        "extension_id": ext_id,
    })
    return read_message(stream)


def test_start_writes_handshake_file(tmp_path):
    hs = tmp_path / "bridge.json"
    bridge = Bridge(hs, on_message=lambda m: None, app_version="9.9.9")
    bridge.start()
    try:
        assert hs.exists()
        data = json.loads(hs.read_text())
        assert data["port"] == bridge.port
        assert data["token"] == bridge.token
        assert "pid" in data
    finally:
        bridge.stop()
    assert not hs.exists()  # removed on stop


def test_good_handshake_and_round_trip(tmp_path):
    received = []
    connects = []
    bridge = Bridge(
        tmp_path / "bridge.json",
        on_message=received.append,
        on_connect=lambda s: connects.append(s),
        app_version="1.2.3",
    )
    bridge.start()
    try:
        sock, stream = _connect(bridge.port)
        ack = _handshake(stream, bridge.token)
        assert ack["type"] == messages.HANDSHAKE_ACK
        assert ack["accepted"] is True
        assert ack["app_version"] == "1.2.3"
        assert _wait(lambda: bridge.is_connected)
        assert _wait(lambda: len(connects) == 1)
        assert connects[0].extension_id == "ext123"

        # client -> app
        write_message(stream, messages.request_tree(request_id="r1"))
        assert _wait(lambda: len(received) == 1)
        assert received[0]["type"] == messages.REQUEST_TREE

        # app -> client
        assert bridge.send(messages.ping(request_id="p1")) is True
        got = read_message(stream)
        assert got["type"] == messages.PING and got["request_id"] == "p1"
    finally:
        bridge.stop()
        sock.close()


def test_bad_token_rejected(tmp_path):
    bridge = Bridge(tmp_path / "bridge.json", on_message=lambda m: None, app_version="1")
    bridge.start()
    try:
        sock, stream = _connect(bridge.port)
        ack = _handshake(stream, "wrong-token")
        assert ack["type"] == messages.HANDSHAKE_ACK
        assert ack["accepted"] is False
        assert not _wait(lambda: bridge.is_connected, timeout=0.5)
    finally:
        bridge.stop()
        sock.close()


def test_send_without_peer_returns_false(tmp_path):
    bridge = Bridge(tmp_path / "bridge.json", on_message=lambda m: None)
    bridge.start()
    try:
        assert bridge.send(messages.ping()) is False
    finally:
        bridge.stop()


def test_second_peer_rejected(tmp_path):
    bridge = Bridge(tmp_path / "bridge.json", on_message=lambda m: None, app_version="1")
    bridge.start()
    try:
        sock1, stream1 = _connect(bridge.port)
        assert _handshake(stream1, bridge.token)["accepted"] is True
        assert _wait(lambda: bridge.is_connected)

        sock2, stream2 = _connect(bridge.port)
        # The bridge drops the second connection without a handshake ack.
        sock2.settimeout(1.0)
        try:
            second = read_message(stream2)
        except OSError:
            second = None
        assert second is None
        sock2.close()
    finally:
        bridge.stop()
        sock1.close()
