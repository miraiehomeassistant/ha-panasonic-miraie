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

    # Ensure OAuth2 implementation is registered
    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        PanasonicMirAIeOAuth2Implementation(hass),
    )

    # Get the OAuth2 implementation for this entry
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

    # Create OAuth2 session for auto token refresh
    oauth_session = config_entry_oauth2_flow.OAuth2Session(
        hass, entry, implementation
    )

    # Ensure the token is valid (triggers refresh if needed)
    try:
        await oauth_session.async_ensure_token_valid()
    except Exception as err:
        _LOGGER.error("Failed to validate/refresh token: %s", err)
        raise ConfigEntryAuthFailed(
            "Authentication failed. Please re-authenticate."
        ) from err

    # Get the current access token
    token_data = entry.data.get("token", {})
    access_token = token_data.get("access_token", "")

    if not access_token:
        raise ConfigEntryAuthFailed("No access token available")

    # Create API client
    session = aiohttp_client.async_get_clientsession(hass)
    api = PanasonicMirAIeAPI(session, access_token)

    # Create coordinator
    coordinator = PanasonicMirAIeCoordinator(
        hass, api, entry, oauth_session
    )

    # Discover devices
    try:
        await coordinator.async_discover_devices()
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(
            "Authentication failed during device discovery"
        ) from err
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Error discovering devices: {err}"
        ) from err

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Store data for platform access
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "oauth_session": oauth_session,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
