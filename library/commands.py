"""Pure parsing of MQTT command payloads and BLE results (no I/O)."""

from ast import literal_eval
from typing import Optional, Tuple, Union

RGB = Tuple[int, int, int]
# A parsed command: "get", an RGB tuple, or a raw string handed to the BLE layer.
Command = Union[str, RGB]


def parse_command(payload: str) -> Optional[Command]:
    """Parse a (lower-cased) MQTT payload.

    Returns "get", a validated RGB tuple, or the raw string (e.g. "on"/"off",
    which the BLE layer interprets). Returns None for a literal that is not a
    valid RGB tuple (wrong shape or channel outside 0-255).
    """
    if payload == "get":
        return payload
    try:
        value = literal_eval(payload)
    except (ValueError, SyntaxError):
        return payload
    if isinstance(value, tuple) and len(value) == 3 and all(
        isinstance(c, int) and 0 <= c <= 255 for c in value
    ):
        return value
    return None


def is_color_result(result: str) -> bool:
    """True if a BLE result string is a stringified 3-tuple, e.g. "(1, 2, 3)".

    Like the original loop, this raises ValueError/SyntaxError for results that
    are not Python literals (e.g. "unknown", "error").
    """
    value = literal_eval(result)
    return isinstance(value, tuple) and len(value) == 3
