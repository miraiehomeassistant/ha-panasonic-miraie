"""Fan platform for Panasonic MirAIe."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN, MANUFACTURER, FAN_POWER, FAN_SPEED, FAN_MODE
from .coordinator import PanasonicMirAIeCoordinator

_LOGGER = logging.getLogger(__name__)

ORDERED_NAMED_FAN_SPEEDS = ["1", "2", "3", "4", "5"]
FAN_PRESET_MODES = ["auto", "normal", "turbo", "sleep"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Panasonic MirAIe fan entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PanasonicMirAIeCoordinator = data["coordinator"]

    entities = []
    for device in coordinator.devices.get("fan", []):
        device_id = device.get("deviceId", "")
        if device_id:
            entities.append(PanasonicFan(coordinator, device))

    if entities:
        _LOGGER.info("Adding %d fan entities", len(entities))
        async_add_entities(entities)


class PanasonicFan(CoordinatorEntity, FanEntity):
    """Panasonic MirAIe fan entity."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = FAN_PRESET_MODES
    _attr_speed_count = len(ORDERED_NAMED_FAN_SPEEDS)
    _enable_turn_on_off_backwards_compat = False

    def __init__(
        self,
        coordinator: PanasonicMirAIeCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator)
        self._device_id = device.get("deviceId", "")
        self._device = device
        self._base_topic = device.get("base_topic")
        self._attr_name = device.get("deviceName", "Panasonic Fan")
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_fan"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device.get("deviceName", "Panasonic Fan"),
            "manufacturer": MANUFACTURER,
            "model": self._device.get("modelId", "MirAIe Fan"),
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
        """Return true if fan is on."""
        return str(self._status.get(FAN_POWER, "off")).lower() == "on"

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if not self.is_on:
            return 0
        speed = self._status.get(FAN_SPEED)
        if speed is not None:
            try:
                speed_str = str(int(speed))
                if speed_str in ORDERED_NAMED_FAN_SPEEDS:
                    return ordered_list_item_to_percentage(
                        ORDERED_NAMED_FAN_SPEEDS, speed_str
                    )
            except (ValueError, TypeError):
                pass
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        mode = str(self._status.get(FAN_MODE, "normal")).lower()
        return mode if mode in FAN_PRESET_MODES else "normal"

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        payload: dict[str, Any] = {FAN_POWER: "on"}
        if percentage is not None:
            speed = percentage_to_ordered_list_item(
                ORDERED_NAMED_FAN_SPEEDS, percentage
            )
            payload[FAN_SPEED] = int(speed)
        if preset_mode is not None:
            payload[FAN_MODE] = preset_mode
        await self._send(payload)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self._send({FAN_POWER: "off"})

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return
        speed = percentage_to_ordered_list_item(
            ORDERED_NAMED_FAN_SPEEDS, percentage
        )
        await self._send({FAN_SPEED: int(speed)})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the fan preset mode."""
        await self._send({FAN_MODE: preset_mode})

    async def _send(self, payload: dict[str, Any]) -> None:
        """Send a control command via MQTT (preferred) or REST."""
        await self.coordinator.async_send_control(
            self._device_id, self._base_topic, payload
        )
