from ast import literal_eval
import asyncio
import logging
from library.config import (
    DEVICE_NAME, CHAR_UUID, CMD_ON, CMD_OFF, COLOR_CMDS,
    MQTT_CONFIG, CMD_TOPIC, STATE_TOPIC, COLOR_TOPIC
)
from library.devices import BLEController
from library.mqtt import MQTTController
from library.persistence import load_strip_state, save_strip_state
import os
from datetime import datetime

# Create log directory structure: Logs > day-level dir > timestamp.log file
log_base_dir = "Logs"
log_day_dir = os.path.join(log_base_dir, datetime.now().strftime("%Y-%m-%d"))
os.makedirs(log_day_dir, exist_ok=True)
log_file = os.path.join(log_day_dir, f"{datetime.now().strftime('%H-%M-%S')}.log")

# Remove basicConfig and set up handlers manually
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s:%(name)s:%(message)s"))
root_logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s:%(name)s:%(message)s"))
root_logger.addHandler(stream_handler)

# Force log file creation immediately
logging.info("Logging initialized. Log file: %s", log_file)

# Load persisted state and color at startup
strip_data = load_strip_state()
strip_state = strip_data["state"]
strip_color = strip_data["color"]

async def main():
    """Run the backend: connect over BLE, start MQTT, and process commands.

    Wires the BLE and MQTT controllers together, then loops over commands
    received from MQTT (on/off, RGB tuple, or "get"), applying them to the
    device and publishing/persisting the resulting state and color.
    """
    command_queue = asyncio.Queue()
    ble = BLEController(
        DEVICE_NAME, CHAR_UUID, CMD_ON, CMD_OFF, COLOR_CMDS,
        current_state=strip_state, current_color=strip_color,
        # device_address="XX:XX:XX:XX:XX:XX"
    )
    mqtt = MQTTController(MQTT_CONFIG, CMD_TOPIC, STATE_TOPIC, COLOR_TOPIC, command_queue)

    if not await ble.scan_and_connect(timeout=20.0):
        return

    mqtt.start(asyncio.get_event_loop())


    try:
        while True:
            command = await command_queue.get()
            # Ensure BLE connection before any command
            ble_retry_count = getattr(main, "ble_retry_count", 5)
            if not await ble.ensure_connected(timeout=10.0):
                ble_retry_count += 1
                setattr(main, "ble_retry_count", ble_retry_count)
                logging.error(f"BLE connection could not be established. Skipping command. Retry {ble_retry_count}/10")
                if ble_retry_count >= 10:
                    logging.error("BLE connection failed 10 times. Exiting application.")
                    os._exit(1)
                continue
            else:
                setattr(main, "ble_retry_count", 0)

            if command == "get":
                mqtt.publish_state(ble.current_state)  # Publish actual state
                mqtt.publish_color(ble.current_color)  # Publish RGB
                continue
            else:
                try:
                    command_eval = literal_eval(command)
                    if isinstance(command_eval, tuple) and len(command_eval) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in command_eval):
                        state = await ble.send_command(command_eval)
                    elif command in ["on", "off"]:
                        state = await ble.send_command(command)
                    else:
                        logging.error(f"Invalid command format: {command}")
                        state = "error"
                except (ValueError, SyntaxError):
                    try:
                        state = await ble.send_command(command)
                    except Exception as e:
                        logging.error(f"BLE error: {e}")
                        state = "error"

            if state in ["on", "off"]:
                mqtt.publish_state(ble.current_state)
                save_strip_state(ble.current_state, ble.current_color)  # Save state
            elif isinstance(literal_eval(state), tuple) and len(literal_eval(state)) == 3:
                mqtt.publish_color(f"{ble.current_color}")
                save_strip_state(ble.current_state, ble.current_color)  # Save color
            else:
                logging.error(f"Unknown state: {state}")
                mqtt.publish_state("unknown")
    except (asyncio.CancelledError, KeyboardInterrupt):
        logging.info("Keyboard interrupt received. Shutting down gracefully...")
    finally:
        await ble.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Program terminated by user.")