"""The Panasonic MirAIe integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
)

from .api import PanasonicMirAIeAPI, AuthenticationError
from .config_flow import PanasonicMirAIeOAuth2Implementation
from .const import DOMAIN
from .coordinator import PanasonicMirAIeCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.FAN, Platform.SWITCH]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Panasonic MirAIe component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Panasonic MirAIe from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        PanasonicMirAIeOAuth2Implementation(hass),
    )

    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
    except ValueError as err:
        _LOGGER.error("OAuth2 implementation not found: %s", err)
        raise ConfigEntryNotReady(
            "OAuth2 implementation not available"
        ) from err

    oauth_session = config_entry_oauth2_flow.OAuth2Session(
        hass, entry, implementation
    )

    try:
        await oauth_session.async_ensure_token_valid()
    except Exception as err:
        _LOGGER.error("Failed to validate/refresh token: %s", err)
        raise ConfigEntryAuthFailed(
            "Authentication failed. Please re-authenticate."
        ) from err

    token_data = entry.data.get("token", {})
    access_token = token_data.get("access_token", "")

    if not access_token:
        raise ConfigEntryAuthFailed("No access token available")

    session = aiohttp_client.async_get_clientsession(hass)
    api = PanasonicMirAIeAPI(session, access_token)

    coordinator = PanasonicMirAIeCoordinator(
        hass, api, entry, oauth_session
    )

    try:
        await coordinator.async_discover_devices()
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(
            "Authentication failed during device discovery"
        ) from err
    except ConfigEntryAuthFailed:
        raise
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Error discovering devices: {err}"
        ) from err

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "oauth_session": oauth_session,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry - ensures MQTT is disconnected cleanly."""
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data is not None:
        coordinator: PanasonicMirAIeCoordinator = data.get("coordinator")
        if coordinator is not None:
            try:
                await coordinator.async_shutdown_mqtt()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error shutting down MQTT: %s", err)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
