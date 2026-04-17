"""Climate platform for Panasonic MirAIe AC."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MANUFACTURER,
    AC_POWER,
    AC_MODE,
    AC_TARGET_TEMP,
    AC_CURRENT_TEMP,
    AC_FAN_SPEED,
    MIRAIE_TO_HA_HVAC,
    HA_TO_MIRAIE_HVAC,
    MIRAIE_TO_HA_FAN,
    HA_TO_MIRAIE_FAN,
)
from .coordinator import PanasonicMirAIeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Panasonic MirAIe climate entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PanasonicMirAIeCoordinator = data["coordinator"]

    entities = []
    for device in coordinator.devices.get("ac", []):
        device_id = device.get("deviceId", "")
        if device_id:
            entities.append(PanasonicClimate(coordinator, device))

    if entities:
        _LOGGER.info("Adding %d AC entities", len(entities))
        async_add_entities(entities)


class PanasonicClimate(CoordinatorEntity, ClimateEntity):
    """Panasonic MirAIe AC climate entity."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.AUTO,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_fan_modes = ["auto", "diffuse", "low", "medium", "high"]
    _enable_turn_on_off_backwards_compat = False

    def __init__(
        self,
        coordinator: PanasonicMirAIeCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._device_id = device.get("deviceId", "")
        self._device = device
        self._base_topic = device.get("base_topic")
        self._attr_name = device.get("deviceName", "Panasonic AC")
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_climate"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device.get("deviceName", "Panasonic AC"),
            "manufacturer": MANUFACTURER,
            "model": self._device.get("modelId", "MirAIe AC"),
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
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        status = self._status
        if str(status.get(AC_POWER, "off")).lower() != "on":
            return HVACMode.OFF
        mode = str(status.get(AC_MODE, "cool")).lower()
        return HVACMode(MIRAIE_TO_HA_HVAC.get(mode, "cool"))

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature."""
        try:
            val = self._status.get(AC_CURRENT_TEMP)
            return float(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        try:
            val = self._status.get(AC_TARGET_TEMP)
            return float(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        fan = str(self._status.get(AC_FAN_SPEED, "auto")).lower()
        return MIRAIE_TO_HA_FAN.get(fan, "auto")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self._send({AC_POWER: "off"})
        else:
            miraie_mode = HA_TO_MIRAIE_HVAC.get(hvac_mode.value, "cool")
            await self._send({AC_POWER: "on", AC_MODE: miraie_mode})

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self._send({AC_TARGET_TEMP: str(temp)})

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        await self._send({AC_FAN_SPEED: HA_TO_MIRAIE_FAN.get(fan_mode, "auto")})

    async def async_turn_on(self) -> None:
        """Turn on the AC."""
        await self._send({AC_POWER: "on"})

    async def async_turn_off(self) -> None:
        """Turn off the AC."""
        await self._send({AC_POWER: "off"})

    async def _send(self, payload: dict[str, Any]) -> None:
        """Send a control command via MQTT (preferred) or REST."""
        await self.coordinator.async_send_control(
            self._device_id, self._base_topic, payload
        )
