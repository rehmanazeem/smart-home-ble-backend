"""
mqtt.py

This module provides the MQTTController class for managing MQTT connections,
subscribing to command topics, publishing state and color updates, and
integrating with an asyncio event loop for command handling.
"""

import logging
import ssl
import threading
import paho.mqtt.client as paho
import asyncio

logger = logging.getLogger("library.mqtt")


class MQTTController:
    """
    MQTTController manages MQTT connections, subscriptions, and publishing for the LED strip.

    Attributes:
        config (dict): MQTT broker configuration.
        cmd_topic (str): Topic for receiving commands.
        state_topic (str): Topic for publishing state.
        color_topic (str): Topic for publishing color.
        command_queue (asyncio.Queue): Queue for passing commands to main loop.
        client (paho.Client): MQTT client for subscribing.
        pub_client (paho.Client): MQTT client for publishing.
    """

    def __init__(self, config, cmd_topic, state_topic, color_topic, command_queue, client_factory=paho.Client):
        """
        Initialize MQTTController.

        Args:
            config (dict): MQTT broker configuration.
            cmd_topic (str): Command topic.
            state_topic (str): State topic.
            color_topic (str): Color topic.
            command_queue (asyncio.Queue): Queue for commands.
            client_factory: Builds the paho clients (seam for tests).
        """
        self.config = config
        self.cmd_topic = cmd_topic
        self.state_topic = state_topic
        self.color_topic = color_topic
        self.command_queue = command_queue
        self.client = client_factory()
        self.pub_client = client_factory()

    def start(self, loop):
        """
        Start MQTT clients for subscribing and publishing.

        Args:
            loop (asyncio.AbstractEventLoop): The asyncio event loop.
        """
        # Configure subscriber client
        self.client.username_pw_set(self.config["username"], self.config["password"])
        self.client.tls_set_context(ssl.create_default_context())
        self.client.user_data_set({'loop': loop})
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.config["host"], self.config["port"])
        threading.Thread(target=self.client.loop_forever, daemon=True).start()

        # Configure publisher client
        self.pub_client.username_pw_set(self.config["username"], self.config["password"])
        self.pub_client.tls_set_context(ssl.create_default_context())
        self.pub_client.connect(self.config["host"], self.config["port"])
        self.pub_client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        """
        Callback for MQTT connection event.

        Args:
            client (paho.Client): The MQTT client.
            userdata (dict): User data.
            flags (dict): Connection flags.
            rc (int): Connection result code.
        """
        logger.info(f"Connected to MQTT broker with result code {rc}")
        client.subscribe(self.cmd_topic)
        # Optionally subscribe to state topic if needed
        # client.subscribe(self.color_topic)

    def on_message(self, client, userdata, msg):
        """
        Callback for received MQTT messages.

        Args:
            client (paho.Client): The MQTT client.
            userdata (dict): User data.
            msg (paho.MQTTMessage): The received message.
        """
        command = msg.payload.decode().strip().lower()
        logger.info(f"Received MQTT command: {command}")
        # Pass command to asyncio queue for main loop processing
        asyncio.run_coroutine_threadsafe(self.command_queue.put(command), userdata['loop'])

    def publish_state(self, state):
        """
        Publish the current state to the state topic.

        Args:
            state (str): The state to publish ("ON", "OFF", etc.).
        """
        self.pub_client.publish(self.state_topic, state.upper())
        logger.info(f"Published state '{state}' to {self.state_topic}")

    def publish_color(self, color):
        """
        Publish the current color to the color topic.

        Args:
            color (str): The color to publish (e.g., "255,165,0" or "RED").
        """
        self.pub_client.publish(self.color_topic, color.upper())
        logger.info(f"Published color '{color}' to {self.color_topic}")