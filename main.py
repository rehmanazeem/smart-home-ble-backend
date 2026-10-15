"""Entry point: bridge MQTT commands to a BLE LED strip."""

import asyncio
import logging
import os

from library.commands import Command, is_color_result, parse_command
from library.config import (
    DEVICE_NAME, CHAR_UUID, CMD_ON, CMD_OFF, COLOR_CMDS,
    MQTT_CONFIG, CMD_TOPIC, STATE_TOPIC, COLOR_TOPIC,
)
from library.devices import BLEController
from library.logging_setup import setup_logging
from library.mqtt import MQTTController
from library.persistence import load_strip_state, save_strip_state

MAX_BLE_FAILURES = 10


async def send_parsed(ble: BLEController, command: str) -> str:
    """Parse an MQTT payload and send it to the strip; return the BLE result."""
    parsed: Command | None = parse_command(command)
    if parsed is None:
        logging.error(f"Invalid command format: {command}")
        return "error"
    if isinstance(parsed, tuple):
        return await ble.send_command(parsed)
    try:
        return await ble.send_command(parsed)
    except Exception as e:
        logging.error(f"BLE error: {e}")
        return "error"


def publish_result(result: str, ble: BLEController, mqtt: MQTTController) -> None:
    """Publish and persist the outcome of a command."""
    if result in ("on", "off"):
        mqtt.publish_state(ble.current_state)
        save_strip_state(ble.current_state, ble.current_color)
    elif is_color_result(result):
        mqtt.publish_color(f"{ble.current_color}")
        save_strip_state(ble.current_state, ble.current_color)
    else:
        logging.error(f"Unknown state: {result}")
        mqtt.publish_state("unknown")


async def handle_command(command: str, ble: BLEController, mqtt: MQTTController) -> None:
    """Apply one MQTT command ("get", on/off, or RGB tuple) and publish the result."""
    if command == "get":
        mqtt.publish_state(ble.current_state)
        mqtt.publish_color(ble.current_color)
        return
    publish_result(await send_parsed(ble, command), ble, mqtt)


async def main() -> None:
    """Connect over BLE, start MQTT, and process queued commands until stopped."""
    strip_data = load_strip_state()
    command_queue: asyncio.Queue = asyncio.Queue()
    ble = BLEController(
        DEVICE_NAME, CHAR_UUID, CMD_ON, CMD_OFF, COLOR_CMDS,
        current_state=strip_data["state"], current_color=strip_data["color"],
        # device_address="XX:XX:XX:XX:XX:XX"
    )
    mqtt = MQTTController(MQTT_CONFIG, CMD_TOPIC, STATE_TOPIC, COLOR_TOPIC, command_queue)

    if not await ble.scan_and_connect(timeout=20.0):
        return

    mqtt.start(asyncio.get_event_loop())

    ble_retry_count = 5  # original starting value, kept as-is
    try:
        while True:
            command = await command_queue.get()
            # Ensure BLE connection before any command
            if not await ble.ensure_connected(timeout=10.0):
                ble_retry_count += 1
                logging.error(f"BLE connection could not be established. Skipping command. Retry {ble_retry_count}/{MAX_BLE_FAILURES}")
                if ble_retry_count >= MAX_BLE_FAILURES:
                    logging.error(f"BLE connection failed {MAX_BLE_FAILURES} times. Exiting application.")
                    os._exit(1)
                continue
            ble_retry_count = 0
            await handle_command(command, ble, mqtt)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info("Keyboard interrupt received. Shutting down gracefully...")
    finally:
        await ble.disconnect()


if __name__ == "__main__":
    setup_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Program terminated by user.")
