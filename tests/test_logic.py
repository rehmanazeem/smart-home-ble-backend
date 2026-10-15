"""Tests for pure logic, using fakes for BLE and MQTT."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main as app
from library import persistence
from library.commands import is_color_result, parse_command
from library.config import CHAR_UUID, CMD_OFF, CMD_ON, parse_rgb_to_bytes
from library.devices import BLEController


class FakeClient:
    is_connected = True

    def __init__(self, address=None):
        self.writes = []

    async def connect(self, timeout=None):
        pass

    async def write_gatt_char(self, uuid, data):
        self.writes.append((uuid, data))


class FakeMQTT:
    def __init__(self):
        self.states, self.colors = [], []

    def publish_state(self, s):
        self.states.append(s)

    def publish_color(self, c):
        self.colors.append(c)


def make_ble():
    ble = BLEController("dev", CHAR_UUID, CMD_ON, CMD_OFF, {})
    ble.client = FakeClient()
    return ble


def test_parse_command():
    assert parse_command("get") == "get"
    assert parse_command("on") == "on"
    assert parse_command("red") == "red"
    assert parse_command("(34, 255, 5)") == (34, 255, 5)
    assert parse_command("(1, 2, 300)") is None
    assert parse_command("(1, 2)") is None
    assert parse_command("5") is None


def test_is_color_result():
    assert is_color_result("(1, 2, 3)")
    assert not is_color_result("(1, 2)")
    assert not is_color_result("unknown")  # non-literal results must not crash the loop


def test_rgb_bytes_clamped():
    assert parse_rgb_to_bytes(1, 2, 3) == bytes.fromhex("7e070503010203" "02ef")
    assert parse_rgb_to_bytes(-5, 999, 0)[4:7] == bytes([0, 255, 0])


def test_ble_send_command():
    ble = make_ble()
    assert asyncio.run(ble.send_command("on")) == "on" and ble.current_state == "ON"
    assert asyncio.run(ble.send_command("off")) == "off" and ble.current_state == "OFF"
    assert asyncio.run(ble.send_command((1, 2, 3))) == "(1, 2, 3)"
    assert ble.current_color == "(1, 2, 3)"
    assert asyncio.run(ble.send_command("red")) == "unknown"
    assert [w[1] for w in ble.client.writes] == [CMD_ON, CMD_OFF, parse_rgb_to_bytes(1, 2, 3)]


def test_ble_scan_and_connect_with_fakes():
    class Dev:
        name, address = "dev", "AA:BB"

    class Scanner:
        @staticmethod
        async def discover(timeout):
            return [Dev()]

    ble = BLEController("dev", CHAR_UUID, CMD_ON, CMD_OFF, {}, current_state="ON",
                        client_factory=FakeClient, scanner=Scanner)
    assert asyncio.run(ble.scan_and_connect()) is True
    assert ble.address == "AA:BB"
    assert ble.client.writes[0][1] == CMD_ON


def test_handle_command(monkeypatch):
    saved = []
    monkeypatch.setattr(app, "save_strip_state", lambda s, c: saved.append((s, c)))
    ble, mqtt = make_ble(), FakeMQTT()

    asyncio.run(app.handle_command("on", ble, mqtt))
    asyncio.run(app.handle_command("(9, 8, 7)", ble, mqtt))
    assert mqtt.states == ["ON"] and mqtt.colors == ["(9, 8, 7)"]
    assert saved == [("ON", (0, 0, 0)), ("ON", "(9, 8, 7)")]

    asyncio.run(app.handle_command("get", ble, mqtt))
    assert mqtt.states[-1] == "ON" and mqtt.colors[-1] == "(9, 8, 7)"


def test_persistence_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(persistence, "PERSISTENCE_FILE", str(tmp_path / "data" / "s.json"))
    assert persistence.load_strip_state() == {"state": "off", "color": "(0, 0, 0)"}
    persistence.save_strip_state("ON", "(1, 2, 3)")
    assert persistence.load_strip_state() == {"state": "ON", "color": "(1, 2, 3)"}
    assert json.loads((tmp_path / "data" / "s.json").read_text())["state"] == "ON"


def test_default_mqtt_client_builds_under_paho_2():
    from library.mqtt import _default_client

    assert _default_client() is not None  # raised ValueError before the callback-version fix


def test_unknown_command_is_reported_not_fatal():
    from library.config import COLOR_CMDS  # noqa: F401  (import check only)
    from main import publish_result

    published = []

    class M:
        def publish_state(self, s): published.append(s)
        def publish_color(self, c): published.append(c)

    class B:
        current_state, current_color = "ON", "(1, 2, 3)"

    publish_result("unknown", B(), M())
    assert published == ["unknown"]
