"""
devices.py

This module provides the BLEController class for managing Bluetooth Low Energy (BLE) connections
and controlling an LED strip device. It supports scanning, connecting, sending color/state commands,
tracking current state and color, and ensuring robust reconnection logic.
"""

import logging
from typing import Any, Callable

from bleak import BleakClient, BleakScanner

from library.commands import parse_rgb
from library.config import parse_rgb_to_bytes

logger = logging.getLogger("library.devices")

class BLEController:
    """
    BLEController manages the connection and communication with a BLE LED strip.

    Attributes:
        device_name (str): Name of the BLE device to connect to.
        char_uuid (str): UUID of the characteristic to write commands to.
        cmd_on (bytes): Command to turn the LED strip ON.
        cmd_off (bytes): Command to turn the LED strip OFF.
        color_cmds (dict): Predefined color commands.
        client (BleakClient): BLE client instance.
        address (str): BLE device address.
        current_state (str): Current ON/OFF state of the LED strip.
        current_color (str or tuple): Current color in RGB format.
    """

    def __init__(self, device_name, char_uuid, cmd_on, cmd_off, color_cmds, device_address=None, current_state="OFF", current_color=(0,0,0),
                 client_factory: Callable[..., Any] = BleakClient, scanner: Any = BleakScanner):
        """
        Initialize BLEController.

        Args:
            device_name (str): BLE device name.
            char_uuid (str): BLE characteristic UUID.
            cmd_on (bytes): ON command.
            cmd_off (bytes): OFF command.
            color_cmds (dict): Dictionary of color commands.
            device_address (str, optional): BLE device address for direct connection.
            client_factory: Builds the BLE client from an address (seam for tests).
            scanner: Object with an async ``discover(timeout=...)`` (seam for tests).
        """
        # Store initialization parameters
        self.device_name = device_name
        self.char_uuid = char_uuid
        self.cmd_on = cmd_on
        self.cmd_off = cmd_off
        self.color_cmds = color_cmds
        self.client = None
        self._client_factory = client_factory
        self._scanner = scanner
        self.address = device_address
        self.current_state = current_state
        self.current_color = current_color

    async def scan_and_connect(self, timeout=5.0):
        """
        Scan for BLE devices and connect to the target device.
        If address is provided, connect directly.

        Args:
            timeout (float): Timeout for scanning/connecting.

        Returns:
            bool: True if connected, False otherwise.
        """
        if self.address:
            # Address known: skip the scan for a faster start
            logger.info(f"[BLE] Connecting directly to address: {self.address}")
        else:
            logger.info("[BLE] Scanning for BLE devices...")
            devices = await self._scanner.discover(timeout=timeout)
            for d in devices:
                logger.info(f"[BLE] Found device: {d.name} [{d.address}]")
            target = next((d for d in devices if d.name == self.device_name), None)
            if not target:
                logger.error(f"[BLE] Device '{self.device_name}' not found.")
                return False
            self.address = target.address

        self.client = self._client_factory(self.address)
        try:
            await self.client.connect(timeout=timeout)
        except Exception as e:
            logger.error(f"[BLE] Connection failed: {e}")
            return False
        if not self.client.is_connected:
            logger.error("[BLE] Failed to connect to the LED strip.")
            return False

        logger.info("[BLE] Successfully connected to the LED strip.")
        await self._restore_state()
        return True

    async def _restore_state(self):
        """Re-apply the persisted on/off state and colour after (re)connecting.

        The colour is persisted as a string such as "(34, 255, 5)", so it is
        parsed back to an RGB tuple before being sent.
        """
        await self.send_command("on" if str(self.current_state).upper() == "ON" else "off")
        logger.info(f"Current state on connect: {self.current_state}")

        color = parse_rgb(self.current_color)
        if color is not None:
            await self.send_command(color)
            logger.info(f"Current color on connect: {color}")

    async def send_command(self, command):
        """
        Send a command to the BLE device.

        Args:
            command (str or tuple): Command string ("on", "off", color name) or RGB tuple.

        Returns:
            str: Resulting state or color string.
        """
        # Ensure BLE client is connected before sending command
        if not self.client or not self.client.is_connected:
            logger.error("BLE client not connected.")
            return "error"
        # Handle ON command
        if command == "on":
            await self.client.write_gatt_char(self.char_uuid, self.cmd_on)
            self.current_state = "ON"
            return "on"
        # Handle OFF command
        elif command == "off":
            await self.client.write_gatt_char(self.char_uuid, self.cmd_off)
            self.current_state = "OFF"
            return "off"
        # Handle RGB tuple command
        elif isinstance(command, tuple) and len(command) == 3:
            await self.client.write_gatt_char(self.char_uuid, parse_rgb_to_bytes(*command))
            self.current_color = f"{command}"
            return f"{command}"
        else:
            return "unknown"

    async def disconnect(self):
        """
        Disconnect the BLE client.
        """
        # Gracefully disconnect BLE client if connected
        if self.client:
            await self.client.__aexit__(None, None, None)
            logger.info("[BLE] Disconnected BLE client.")

    async def ensure_connected(self, timeout=10.0):
        """
        Ensure BLE connection is active. Attempt to reconnect if disconnected.

        Args:
            timeout (float): Timeout for reconnection.

        Returns:
            bool: True if connected, False otherwise.
        """
        # Check connection status and reconnect if needed
        if not self.client or not self.client.is_connected:
            logger.info("[BLE] Not connected. Attempting to reconnect...")
            if self.address:
                try:
                    if self.client is None:  # never created (e.g. address given, first connect failed early)
                        self.client = self._client_factory(self.address)
                    await self.client.connect(timeout=timeout)
                    logger.info("[BLE] Reconnected successfully.")
                except Exception as e:
                    logger.error(f"[BLE] Reconnection failed: {e}")
                    return False
            else:
                logger.error("[BLE] No address available for reconnection.")
                return False
        return True
