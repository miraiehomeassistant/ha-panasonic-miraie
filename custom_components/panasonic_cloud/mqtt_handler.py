"""MQTT handler for Panasonic MirAIe real-time updates.

Connects to Panasonic's production MQTT broker at mqtt.miraie.in:8883
using homeId as username and OAuth access_token as password.

Subscribes to device state topics and dispatches updates to the coordinator.
Publishes control commands directly to device topics (faster than REST).

Runs paho-mqtt in its own thread (standard paho design) and marshals
incoming messages back to the HA event loop via run_coroutine_threadsafe.
"""
from __future__ import annotations

import asyncio
import json
import logging
import ssl
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

from .const import (
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_KEEPALIVE,
    MQTT_RECONNECT_MIN_DELAY,
    MQTT_RECONNECT_MAX_DELAY,
)

_LOGGER = logging.getLogger(__name__)


class PanasonicMirAIeMQTT:
    """Manage the MQTT connection to the Panasonic MirAIe broker."""

    def __init__(
        self,
        hass_loop: asyncio.AbstractEventLoop,
        home_id: str,
        access_token: str,
        on_state_update: Callable[[str, dict[str, Any]], None],
        on_connection_update: Callable[[str, bool], None] | None = None,
    ) -> None:
        """Initialize the MQTT handler.

        Args:
            hass_loop: The Home Assistant event loop (for marshalling callbacks).
            home_id: The MirAIe home ID (used as MQTT username).
            access_token: The OAuth2 access token (used as MQTT password).
            on_state_update: Called as (device_id, payload_dict) when a
                             status message arrives.
            on_connection_update: Called as (device_id, is_online) when a
                                  connectionStatus message arrives.
        """
        self._loop = hass_loop
        self._home_id = home_id
        self._access_token = access_token
        self._on_state_update = on_state_update
        self._on_connection_update = on_connection_update

        self._client: mqtt.Client | None = None
        self._connected = False
        self._stopping = False
        self._subscriptions: set[str] = set()
        self._consecutive_disconnects = 0

    @property
    def is_connected(self) -> bool:
        """Return whether the client currently reports connected."""
        return self._connected

    async def async_connect(self) -> bool:
        """Connect to the MQTT broker.

        Returns True on successful connection, False otherwise.
        Does NOT raise - coordinator can decide to continue with REST-only.
        """
        client_id = f"ha-miraie-{self._home_id}"
        self._client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )

        # ssl.create_default_context() reads cert files from disk and
        # blocks the event loop - run it in an executor.
        def _build_ssl_context() -> ssl.SSLContext:
            ctx = ssl.create_default_context()
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            return ctx

        ssl_context = await self._loop.run_in_executor(None, _build_ssl_context)
        self._client.tls_set_context(ssl_context)

        self._client.username_pw_set(
            username=self._home_id,
            password=self._access_token,
        )

        self._client.reconnect_delay_set(
            min_delay=MQTT_RECONNECT_MIN_DELAY,
            max_delay=MQTT_RECONNECT_MAX_DELAY,
        )

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        try:
            _LOGGER.info(
                "Connecting to MQTT broker %s:%s as %s",
                MQTT_BROKER,
                MQTT_PORT,
                self._home_id,
            )
            await self._loop.run_in_executor(
                None,
                lambda: self._client.connect(
                    MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE
                ),
            )
            self._client.loop_start()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("MQTT connect failed: %s", err)
            return False

        # Wait up to 5 seconds for connection callback
        for _ in range(10):
            if self._connected:
                return True
            await asyncio.sleep(0.5)

        _LOGGER.warning("MQTT connection timed out after 5s")
        return False

    async def async_disconnect(self) -> None:
        """Disconnect cleanly and stop the background thread."""
        self._stopping = True
        if self._client is not None:
            try:
                await self._loop.run_in_executor(None, self._client.disconnect)
                self._client.loop_stop()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error during MQTT disconnect: %s", err)
        self._connected = False
        _LOGGER.info("MQTT handler stopped")

    async def async_update_token(self, access_token: str) -> None:
        """Update the access token and reconnect with the new credentials."""
        if access_token == self._access_token:
            return
        _LOGGER.debug("MQTT token updated - reconnecting")
        self._access_token = access_token
        if self._client is not None:
            self._client.username_pw_set(
                username=self._home_id,
                password=self._access_token,
            )
            try:
                await self._loop.run_in_executor(None, self._client.reconnect)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("MQTT reconnect after token refresh failed: %s", err)

    def subscribe_topics(self, topics: list[str]) -> None:
        """Subscribe to the given list of device base topics.

        For each base topic, subscribes to both {topic}/status and
        {topic}/connectionStatus. Topics already subscribed are skipped.
        """
        if self._client is None or not self._connected:
            _LOGGER.debug("MQTT not connected - deferring subscribe")
            return

        new_count = 0
        for base in topics:
            for suffix in ("/status", "/connectionStatus"):
                full = base + suffix
                if full in self._subscriptions:
                    continue
                self._client.subscribe(full, qos=0)
                self._subscriptions.add(full)
                new_count += 1

        if new_count:
            _LOGGER.info(
                "Subscribed to %d new MQTT topics (%d total)",
                new_count,
                len(self._subscriptions),
            )

    def publish_control(self, base_topic: str, payload: dict[str, Any]) -> bool:
        """Publish a control command to {base_topic}/control.

        Payload is wrapped with the standard cnt/sid fields if missing.
        Returns True on successful publish.
        """
        if self._client is None or not self._connected:
            _LOGGER.debug("MQTT not connected - cannot publish control")
            return False

        wrapped = {
            "cnt": "an",
            "sid": "0",
            **payload,
        }
        topic = f"{base_topic}/control"
        try:
            result = self._client.publish(topic, json.dumps(wrapped), qos=1)
            _LOGGER.debug("MQTT publish to %s: %s", topic, wrapped)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("MQTT publish failed: %s", err)
            return False

    # --- paho callbacks (run in paho's own thread) ---

    def _on_connect(self, client, userdata, flags, rc) -> None:
        """Handle successful or failed connection."""
        if rc == 0:
            self._connected = True
            self._consecutive_disconnects = 0
            _LOGGER.info("MQTT connected to %s", MQTT_BROKER)
            # Re-subscribe after reconnect
            for topic in self._subscriptions:
                client.subscribe(topic, qos=0)
        else:
            self._connected = False
            _LOGGER.warning("MQTT connect failed with code %s", rc)

    def _on_disconnect(self, client, userdata, rc) -> None:
        """Handle disconnect.

        Idle-timeout disconnects (rc=7) from the Panasonic broker are
        normal and paho will auto-reconnect within a few seconds. We only
        escalate to a WARNING if reconnects keep failing.
        """
        self._connected = False
        if self._stopping:
            return
        if rc == 0:
            return
        self._consecutive_disconnects += 1
        if self._consecutive_disconnects >= 3:
            _LOGGER.warning(
                "MQTT disconnected %d times in a row (last rc=%s) - "
                "broker may be unreachable",
                self._consecutive_disconnects,
                rc,
            )
        else:
            _LOGGER.debug(
                "MQTT disconnected (rc=%s) - auto-reconnecting", rc
            )

    def _on_message(self, client, userdata, msg) -> None:
        """Handle incoming message - dispatch to HA event loop."""
        try:
            topic = msg.topic
            payload_bytes = msg.payload
            # Dispatch to HA loop
            asyncio.run_coroutine_threadsafe(
                self._handle_message(topic, payload_bytes),
                self._loop,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error dispatching MQTT message: %s", err)

    async def _handle_message(self, topic: str, payload_bytes: bytes) -> None:
        """Parse a message and invoke the appropriate callback.

        Topic format: {prefix-uuid}/{home_id}/{device_id}/{suffix}
        We extract device_id as the third path segment.
        """
        try:
            payload_str = payload_bytes.decode("utf-8")
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                _LOGGER.debug("Non-JSON MQTT payload on %s", topic)
                return

            parts = topic.split("/")
            if len(parts) < 4:
                return
            device_id = parts[2]
            suffix = parts[3]

            if suffix == "status":
                self._on_state_update(device_id, payload)
            elif suffix == "connectionStatus" and self._on_connection_update:
                online = str(payload.get("onlineStatus", "false")).lower() == "true"
                self._on_connection_update(device_id, online)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error handling MQTT message: %s", err)
