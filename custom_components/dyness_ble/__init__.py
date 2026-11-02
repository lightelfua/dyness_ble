"""The Dyness CAN BLE integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .coordinator import DynessBLECoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type DynessBLEConfigEntry = ConfigEntry[DynessBLECoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DynessBLEConfigEntry) -> bool:
    """Set up Dyness CAN BLE from a config entry."""
    coordinator = DynessBLECoordinator(hass, entry, entry.data[CONF_ADDRESS])
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DynessBLEConfigEntry) -> bool:
    """Unload a config entry and free the BLE link."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
    return unload_ok
