"""Switch platform for Panasonic MirAIe."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MANUFACTURER,
    SWITCH_POWER,
    SWITCH_STATES,
    SWITCH_CHANNEL,
    SWITCH_CH_STATE,
)
from .coordinator import PanasonicMirAIeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Panasonic MirAIe switch entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PanasonicMirAIeCoordinator = data["coordinator"]

    entities = []
    for device in coordinator.devices.get("switch", []):
        device_id = device.get("deviceId", "")
        if not device_id:
            continue

        status = coordinator.device_status.get(device_id, {})
        states = status.get(SWITCH_STATES, [])

        if states and len(states) > 1:
            for i, channel in enumerate(states):
                ch_num = channel.get(SWITCH_CHANNEL, f"{i:02d}")
                entities.append(
                    PanasonicSwitch(coordinator, device, ch_num)
                )
        else:
            entities.append(PanasonicSwitch(coordinator, device, None))

    if entities:
        _LOGGER.info("Adding %d switch entities", len(entities))
        async_add_entities(entities)


class PanasonicSwitch(CoordinatorEntity, SwitchEntity):
    """Panasonic MirAIe switch entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PanasonicMirAIeCoordinator,
        device: dict[str, Any],
        channel: str | None,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._device_id = device.get("deviceId", "")
        self._device = device
        self._channel = channel
        self._base_topic = device.get("base_topic")

        device_name = device.get("deviceName", "Panasonic Switch")
        if channel is not None:
            self._attr_name = f"{device_name} Ch {int(channel) + 1}"
            self._attr_unique_id = f"{DOMAIN}_{self._device_id}_switch_ch{channel}"
        else:
            self._attr_name = device_name
            self._attr_unique_id = f"{DOMAIN}_{self._device_id}_switch"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device.get("deviceName", "Panasonic Switch"),
            "manufacturer": MANUFACTURER,
            "model": self._device.get("modelId", "MirAIe Switch"),
        }

    @property
    def _status(self) -> dict[str, Any]:
        """Get current device status from coordinator."""
        return self.coordinator.device_status.get(self._device_id, {})

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        status = self._status
        if not status:
            return False
        return str(status.get("onlineStatus", "true")).lower() == "true"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if self._channel is not None:
            for ch in self._status.get(SWITCH_STATES, []):
                if ch.get(SWITCH_CHANNEL) == self._channel:
                    return str(ch.get(SWITCH_CH_STATE, "off")).lower() == "on"
            return False
        return str(self._status.get(SWITCH_POWER, "off")).lower() == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        if self._channel is not None:
            await self._send_channel("on")
        else:
            await self._send({SWITCH_POWER: "on"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        if self._channel is not None:
            await self._send_channel("off")
        else:
            await self._send({SWITCH_POWER: "off"})

    async def _send_channel(self, state: str) -> None:
        """Send a command for a specific channel."""
        states = list(self._status.get(SWITCH_STATES, []))
        found = False
        for ch in states:
            if ch.get(SWITCH_CHANNEL) == self._channel:
                ch[SWITCH_CH_STATE] = state
                found = True
                break
        if not found:
            states.append({SWITCH_CHANNEL: self._channel, SWITCH_CH_STATE: state})
        await self._send({SWITCH_POWER: "on", SWITCH_STATES: states})

    async def _send(self, payload: dict[str, Any]) -> None:
        """Send a control command via MQTT (preferred) or REST."""
        await self.coordinator.async_send_control(
            self._device_id, self._base_topic, payload
        )
