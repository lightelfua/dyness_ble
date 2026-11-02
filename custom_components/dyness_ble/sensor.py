"""Sensors for the Dyness CAN BLE integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DynessBLEConfigEntry
from .const import DOMAIN, NOMINAL_VOLTAGE
from .coordinator import DynessBLECoordinator

PARALLEL_UPDATES = 0

Data = dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class DynessSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor."""

    value_fn: Callable[[Data], float | str | None]


def _raw(key: str) -> Callable[[Data], float | str | None]:
    return lambda data: data.get(key)


def _remaining_energy(data: Data) -> float | None:
    ah = data.get("remaining_capacity")
    return None if ah is None else ah * NOMINAL_VOLTAGE / 1000


MEASURE = SensorStateClass.MEASUREMENT
DIAG = EntityCategory.DIAGNOSTIC
VOLT = UnitOfElectricPotential.VOLT
AMP = UnitOfElectricCurrent.AMPERE
WATT = UnitOfPower.WATT

SENSORS: tuple[DynessSensorDescription, ...] = (
    DynessSensorDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=VOLT,
        state_class=MEASURE,
        suggested_display_precision=2,
        value_fn=_raw("voltage"),
    ),
    DynessSensorDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=AMP,
        state_class=MEASURE,
        suggested_display_precision=1,
        value_fn=_raw("current"),
    ),
    DynessSensorDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=WATT,
        state_class=MEASURE,
        suggested_display_precision=0,
        value_fn=_raw("power"),
    ),
    DynessSensorDescription(
        key="soc",
        translation_key="soc",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=MEASURE,
        suggested_display_precision=0,
        value_fn=_raw("soc"),
    ),
    DynessSensorDescription(
        key="soh",
        translation_key="soh",
        icon="mdi:battery-heart-variant",
        native_unit_of_measurement=PERCENTAGE,
        state_class=MEASURE,
        suggested_display_precision=0,
        value_fn=_raw("soh"),
    ),
    DynessSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEASURE,
        suggested_display_precision=1,
        value_fn=_raw("temperature"),
    ),
    DynessSensorDescription(
        key="remaining_capacity",
        translation_key="remaining_capacity",
        icon="mdi:battery",
        native_unit_of_measurement="Ah",
        state_class=MEASURE,
        suggested_display_precision=0,
        value_fn=_raw("remaining_capacity"),
    ),
    DynessSensorDescription(
        key="remaining_energy",
        translation_key="remaining_energy",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=MEASURE,
        suggested_display_precision=2,
        value_fn=_remaining_energy,
    ),
    DynessSensorDescription(
        key="charging_power",
        translation_key="charging_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=WATT,
        state_class=MEASURE,
        suggested_display_precision=0,
        value_fn=_raw("charging_power"),
    ),
    DynessSensorDescription(
        key="discharging_power",
        translation_key="discharging_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=WATT,
        state_class=MEASURE,
        suggested_display_precision=0,
        value_fn=_raw("discharging_power"),
    ),
    DynessSensorDescription(
        key="charge_voltage_limit",
        translation_key="charge_voltage_limit",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=VOLT,
        state_class=MEASURE,
        entity_category=DIAG,
        suggested_display_precision=1,
        value_fn=_raw("charge_voltage_limit"),
    ),
    DynessSensorDescription(
        key="charge_current_limit",
        translation_key="charge_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=AMP,
        state_class=MEASURE,
        entity_category=DIAG,
        suggested_display_precision=1,
        value_fn=_raw("charge_current_limit"),
    ),
    DynessSensorDescription(
        key="discharge_current_limit",
        translation_key="discharge_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=AMP,
        state_class=MEASURE,
        entity_category=DIAG,
        suggested_display_precision=1,
        value_fn=_raw("discharge_current_limit"),
    ),
    DynessSensorDescription(
        key="discharge_voltage_limit",
        translation_key="discharge_voltage_limit",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=VOLT,
        state_class=MEASURE,
        entity_category=DIAG,
        suggested_display_precision=1,
        value_fn=_raw("discharge_voltage_limit"),
    ),
    DynessSensorDescription(
        key="battery_name",
        translation_key="battery_name",
        icon="mdi:tag-text-outline",
        entity_category=DIAG,
        value_fn=_raw("battery_name"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DynessBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dyness sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        DynessSensor(coordinator, entry, description) for description in SENSORS
    )


class DynessSensor(CoordinatorEntity[DynessBLECoordinator], SensorEntity):
    """A single value pushed by the ESP32 gateway."""

    _attr_has_entity_name = True
    entity_description: DynessSensorDescription

    def __init__(
        self,
        coordinator: DynessBLECoordinator,
        entry: DynessBLEConfigEntry,
        description: DynessSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        address = coordinator.address
        self._attr_unique_id = f"{address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(CONNECTION_BLUETOOTH, address)},
            name=entry.title,
            manufacturer="DIY",
            model="Dyness CAN BLE",
        )

    @property
    def available(self) -> bool:
        """Available while the GATT link is up."""
        return self.coordinator.connected

    @property
    def native_value(self) -> float | str | None:
        """Return the latest value."""
        return self.entity_description.value_fn(self.coordinator.data)
