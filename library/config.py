import os

DEVICE_NAME = "ELK-BLEDOB"
CHAR_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

CMD_ON  = bytes.fromhex("7e0704ff00010201ef")
CMD_OFF = bytes.fromhex("7e07040000000201ef")
COLOR_CMDS = {
    "red":    bytes.fromhex("7e070503ff000002ef"),
    "green":  bytes.fromhex("7e07050300ff0002ef"),
    "blue":   bytes.fromhex("7e0705030000ff02ef"),
    "yellow": bytes.fromhex("7e070503ffff0002ef"),
    "cyan":   bytes.fromhex("7e07050300ffff02ef"),
    "magenta":bytes.fromhex("7e070503ff00ff02ef"),
    "white":  bytes.fromhex("7e070503ffffff02ef"),
}

MQTT_CONFIG = {
    "host": os.getenv("MQTT_HOST", "your-broker.hivemq.cloud"),
    "port": int(os.getenv("MQTT_PORT", "8883")),
    "username": os.getenv("MQTT_USERNAME", ""),
    "password": os.getenv("MQTT_PASSWORD", ""),
}

CMD_TOPIC = "home/strip/set"
STATE_TOPIC = "home/strip/state"
COLOR_TOPIC = "home/strip/color"

def parse_rgb_to_bytes(r: int, g: int, b: int) -> bytes:
    """Return bytes command for given RGB values (0-255 each)."""
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    return bytes([0x7e, 0x07, 0x05, 0x03, r, g, b, 0x02, 0xef])
