"""Data update coordinator for Panasonic MirAIe.

v1.1.0 changes:
- MQTT real-time updates via PanasonicMirAIeMQTT
- REST polling reduced to 15 minute fallback (was 5 minutes)
- MQTT state updates push directly into device_status and trigger HA state refresh
- On token refresh, MQTT credentials are updated and reconnection happens
"""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import PanasonicMirAIeAPI, AuthenticationError
from .const import DOMAIN, SCAN_INTERVAL_SECONDS
from .mqtt_handler import PanasonicMirAIeMQTT

_LOGGER = logging.getLogger(__name__)


class PanasonicMirAIeCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Panasonic MirAIe data from REST + MQTT."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: PanasonicMirAIeAPI,
        entry: ConfigEntry,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.api = api
        self.entry = entry
        self.oauth_session = oauth_session
        self.devices: dict[str, list[dict[str, Any]]] = {
            "ac": [],
            "fan": [],
            "switch": [],
        }
        self.device_status: dict[str, dict[str, Any]] = {}
        self.home_id: str | None = None
        self.topics: list[str] = []
        self.mqtt: PanasonicMirAIeMQTT | None = None

    async def _async_ensure_fresh_token(self) -> None:
        """Ensure the token is valid; update API client and MQTT if refreshed."""
        try:
            await self.oauth_session.async_ensure_token_valid()
        except Exception as err:
            _LOGGER.error("Token refresh failed: %s", err)
            raise ConfigEntryAuthFailed(
                "Token refresh failed. Please re-authenticate."
            ) from err

        token_data = self.entry.data.get("token", {})
        current_token = token_data.get("access_token", "")
        if current_token and current_token != self.api.access_token:
            self.api.set_token(current_token)
            # Push new token to MQTT too
            if self.mqtt is not None:
                await self.mqtt.async_update_token(current_token)

    async def async_discover_devices(self) -> None:
        """Discover all devices, then start MQTT.

        MQTT startup is best-effort: if it fails, we log and continue
        with REST polling only.
        """
        await self._async_ensure_fresh_token()
        try:
            data = await self.api.async_get_devices()
            self.devices = {
                "ac": data.get("ac", []),
                "fan": data.get("fan", []),
                "switch": data.get("switch", []),
            }
            self.home_id = data.get("home_id")
            self.topics = data.get("topics", [])
            _LOGGER.info(
                "Discovered %d AC, %d Fan, %d Switch devices; home_id=%s",
                len(self.devices["ac"]),
                len(self.devices["fan"]),
                len(self.devices["switch"]),
                self.home_id,
            )
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed during discovery"
            ) from err
        except Exception as err:
            raise UpdateFailed(f"Error discovering devices: {err}") from err

        # Start MQTT (best effort - REST fallback remains)
        await self._async_start_mqtt()

    async def _async_start_mqtt(self) -> None:
        """Start the MQTT handler. Failure is non-fatal."""
        if not self.home_id:
            _LOGGER.warning("No home_id - skipping MQTT setup")
            return
        if not self.topics:
            _LOGGER.warning("No device topics - skipping MQTT setup")
            return

        self.mqtt = PanasonicMirAIeMQTT(
            hass_loop=self.hass.loop,
            home_id=self.home_id,
            access_token=self.api.access_token,
            on_state_update=self._handle_mqtt_state,
            on_connection_update=self._handle_mqtt_connection,
        )
        connected = await self.mqtt.async_connect()
        if connected:
            self.mqtt.subscribe_topics(self.topics)
            _LOGGER.info("MQTT real-time updates active")
        else:
            _LOGGER.warning(
                "MQTT connect failed - falling back to REST polling only"
            )

    async def async_shutdown_mqtt(self) -> None:
        """Stop the MQTT handler cleanly."""
        if self.mqtt is not None:
            await self.mqtt.async_disconnect()
            self.mqtt = None

    def _handle_mqtt_state(self, device_id: str, payload: dict[str, Any]) -> None:
        """Apply an MQTT state update and notify listening entities.

        Runs in the HA event loop (dispatched from MQTT thread).
        """
        if not device_id:
            return

        existing = self.device_status.get(device_id, {})
        existing.update(payload)
        self.device_status[device_id] = existing

        # Push to entities without hitting the API
        self.async_set_updated_data(self.device_status)

    def _handle_mqtt_connection(self, device_id: str, online: bool) -> None:
        """Apply an MQTT connection-status update."""
        if not device_id:
            return
        existing = self.device_status.get(device_id, {})
        existing["onlineStatus"] = "true" if online else "false"
        self.device_status[device_id] = existing
        self.async_set_updated_data(self.device_status)

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch latest status for all devices via REST (fallback).

        With MQTT active, this runs every 15 minutes as a safety net.
        Without MQTT, it's the primary update path.

        If a device call returns 401, we force a token refresh and retry
        once - this catches the case where Panasonic invalidated the
        token earlier than its declared expiry.
        """
        await self._async_ensure_fresh_token()

        all_devices = []
        for device_type in ("ac", "fan", "switch"):
            all_devices.extend(self.devices.get(device_type, []))

        if not all_devices:
            return self.device_status

        retried = False
        for device in all_devices:
            device_id = device.get("deviceId", "")
            if not device_id:
                continue
            try:
                status = await self.api.async_get_device_status(device_id)
                if status:
                    existing = self.device_status.get(device_id, {})
                    existing.update(status)
                    self.device_status[device_id] = existing
            except AuthenticationError as err:
                if not retried:
                    _LOGGER.info(
                        "Got 401 on %s - forcing token refresh and retrying",
                        device_id,
                    )
                    retried = True
                    try:
                        await self._async_ensure_fresh_token()
                        status = await self.api.async_get_device_status(
                            device_id
                        )
                        if status:
                            existing = self.device_status.get(device_id, {})
                            existing.update(status)
                            self.device_status[device_id] = existing
                        continue
                    except Exception:  # noqa: BLE001
                        pass
                raise ConfigEntryAuthFailed(
                    "Authentication failed during update"
                ) from err
            except Exception as err:
                _LOGGER.warning("Error updating %s: %s", device_id, err)

        return self.device_status

    async def async_send_control(
        self, device_id: str, base_topic: str | None, payload: dict[str, Any]
    ) -> bool:
        """Send a control command.

        Prefers MQTT (faster) with REST fallback. Always updates local
        state optimistically so the UI feels instant.
        """
        # Optimistic local update
        existing = self.device_status.get(device_id, {})
        existing.update(payload)
        self.device_status[device_id] = existing
        self.async_set_updated_data(self.device_status)

        # Try MQTT first
        if self.mqtt is not None and self.mqtt.is_connected and base_topic:
            if self.mqtt.publish_control(base_topic, payload):
                return True
            _LOGGER.debug("MQTT publish failed, falling back to REST")

        # REST fallback
        return await self.api.async_set_device_state(device_id, payload)
