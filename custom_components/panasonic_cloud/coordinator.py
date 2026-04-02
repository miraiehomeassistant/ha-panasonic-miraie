"""Data update coordinator for Panasonic MirAIe."""
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

_LOGGER = logging.getLogger(__name__)


class PanasonicMirAIeCoordinator(DataUpdateCoordinator):
    """Coordinator to manage fetching Panasonic MirAIe data."""

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

    async def _async_ensure_fresh_token(self) -> None:
        """Ensure the token is valid and update the API client if refreshed."""
        try:
            await self.oauth_session.async_ensure_token_valid()
        except Exception as err:
            _LOGGER.error("Token refresh failed: %s", err)
            raise ConfigEntryAuthFailed(
                "Token refresh failed. Please re-authenticate."
            ) from err

        # Update the API client with the (possibly refreshed) token
        token_data = self.entry.data.get("token", {})
        current_token = token_data.get("access_token", "")
        if current_token:
            self.api.set_token(current_token)

    async def async_discover_devices(self) -> None:
        """Discover all devices from the API."""
        await self._async_ensure_fresh_token()
        try:
            self.devices = await self.api.async_get_devices()
            _LOGGER.info(
                "Discovered %d AC, %d Fan, %d Switch devices",
                len(self.devices.get("ac", [])),
                len(self.devices.get("fan", [])),
                len(self.devices.get("switch", [])),
            )
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed during discovery"
            ) from err
        except Exception as err:
            raise UpdateFailed(f"Error discovering devices: {err}") from err

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch latest status for all devices."""
        await self._async_ensure_fresh_token()

        all_devices = []
        for device_type in ("ac", "fan", "switch"):
            all_devices.extend(self.devices.get(device_type, []))

        if not all_devices:
            return self.device_status

        for device in all_devices:
            device_id = device.get("deviceId", "")
            if not device_id:
                continue
            try:
                status = await self.api.async_get_device_status(device_id)
                if status:
                    self.device_status[device_id] = status
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed(
                    "Authentication failed during update"
                ) from err
            except Exception as err:
                _LOGGER.warning("Error updating %s: %s", device_id, err)

        return self.device_status
