"""API client for Panasonic MirAIe."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import (
    HOMES_URL,
    STATUS_URL,
    CONTROL_URL,
    AC_CATEGORIES,
    FAN_CATEGORIES,
    SWITCH_CATEGORIES,
)

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class PanasonicMirAIeAPI:
    """API client for Panasonic MirAIe."""

    def __init__(self, session: aiohttp.ClientSession, access_token: str) -> None:
        """Initialize the API client."""
        self._session = session
        self._access_token = access_token

    def set_token(self, access_token: str) -> None:
        """Update the access token."""
        self._access_token = access_token

    def _headers(self) -> dict[str, str]:
        """Return request headers with current token."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _check_auth_error(self, status: int, device_id: str = "") -> None:
        """Raise AuthenticationError for auth-related HTTP status codes."""
        if status in (401, 406):
            context = f" for {device_id}" if device_id else ""
            _LOGGER.error("Authentication error (%s)%s", status, context)
            raise AuthenticationError(f"HTTP {status}: Token invalid or expired")

    async def async_get_homes(self) -> list[dict[str, Any]]:
        """Get all homes and their devices."""
        try:
            async with self._session.get(
                HOMES_URL, headers=self._headers()
            ) as resp:
                self._check_auth_error(resp.status)

                if resp.status == 502:
                    _LOGGER.warning("Homes API 502 - server temporarily unavailable")
                    return []
                if resp.status == 404:
                    _LOGGER.error("Homes API 404 - endpoint not found: %s", HOMES_URL)
                    return []

                resp.raise_for_status()
                data = await resp.json()

                # API returns dict for single home, list for multiple
                if isinstance(data, dict):
                    if "message" in data:
                        _LOGGER.error("Homes API error: %s", data["message"])
                        return []
                    return [data]
                return data if isinstance(data, list) else [data]

        except AuthenticationError:
            raise
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching homes: %s", err)
            raise

    async def async_get_devices(self) -> dict[str, list[dict[str, Any]]]:
        """Get all devices grouped by type.

        API structure: home -> spaces[] -> devices[]
        Each device has: deviceId, deviceName, category, modelId, topic
        """
        homes = await self.async_get_homes()

        ac_devices: list[dict[str, Any]] = []
        fan_devices: list[dict[str, Any]] = []
        switch_devices: list[dict[str, Any]] = []

        for home in homes:
            home_id = home.get("homeId", "unknown")
            home_name = home.get("homeName", "Unknown Home")
            spaces = home.get("spaces", [])

            _LOGGER.debug(
                "Home '%s' (%s) has %d spaces", home_name, home_id, len(spaces)
            )

            for space in spaces:
                space_name = space.get("spaceName", "Unknown Space")
                devices = space.get("devices", [])

                for device in devices:
                    device_id = device.get("deviceId", "")
                    device_name = device.get("deviceName", "Unknown Device")
                    category = device.get("category", "").upper()

                    if not device_id:
                        continue

                    # Enrich device data with home/space context
                    device["homeId"] = home_id
                    device["homeName"] = home_name
                    device["spaceName"] = space_name
                    device["name"] = device_name

                    if category in AC_CATEGORIES:
                        ac_devices.append(device)
                    elif category in FAN_CATEGORIES:
                        fan_devices.append(device)
                    elif category in SWITCH_CATEGORIES:
                        switch_devices.append(device)
                    else:
                        _LOGGER.debug(
                            "Skipping '%s' (category: %s)", device_name, category
                        )

        _LOGGER.info(
            "Discovered: %d AC, %d Fan, %d Switch",
            len(ac_devices), len(fan_devices), len(switch_devices),
        )
        return {"ac": ac_devices, "fan": fan_devices, "switch": switch_devices}

    async def async_get_device_status(self, device_id: str) -> dict[str, Any]:
        """Get the current status of a device."""
        url = STATUS_URL(device_id)
        try:
            async with self._session.get(url, headers=self._headers()) as resp:
                self._check_auth_error(resp.status, device_id)

                if resp.status == 403:
                    _LOGGER.debug(
                        "Status API 403 for %s - device may not support status queries",
                        device_id,
                    )
                    return {}
                if resp.status in (404, 502):
                    _LOGGER.debug("Status API %s for %s", resp.status, device_id)
                    return {}

                resp.raise_for_status()
                return await resp.json()

        except AuthenticationError:
            raise
        except aiohttp.ClientError as err:
            _LOGGER.warning("Error fetching status for %s: %s", device_id, err)
            return {}

    async def async_set_device_state(
        self, device_id: str, payload: dict[str, Any]
    ) -> bool:
        """Set device state via the control API.

        Wraps payload in the required format:
        {
            "deviceId": "<id>",
            "control_params": {
                "cnt": "an",
                "sid": "0",
                ... state fields ...
            }
        }
        """
        url = CONTROL_URL(device_id)
        control_payload = {
            "deviceId": device_id,
            "control_params": {
                "cnt": "an",
                "sid": "0",
                **payload,
            },
        }

        try:
            async with self._session.post(
                url, headers=self._headers(), json=control_payload
            ) as resp:
                self._check_auth_error(resp.status, device_id)

                if resp.status == 400:
                    resp_text = await resp.text()
                    _LOGGER.error(
                        "Control 400 for %s: %s", device_id, resp_text[:200]
                    )
                    return False
                if resp.status in (403, 502):
                    _LOGGER.warning("Control %s for %s", resp.status, device_id)
                    return False

                resp.raise_for_status()
                _LOGGER.debug("Control success for %s: %s", device_id, payload)
                return True

        except AuthenticationError:
            raise
        except aiohttp.ClientError as err:
            _LOGGER.error("Error controlling %s: %s", device_id, err)
            return False
