"""Constants for the Dyness CAN BLE integration."""

from __future__ import annotations

DOMAIN = "dyness_ble"

# Must match `services[0].uuid` in the ESPHome firmware.
SERVICE_UUID = "7aab0001-7aab-4535-af3e-ee76a35cc42d"
LOCAL_NAME_PREFIX = "ble-dyness-can"

# data key -> GATT characteristic UUID (see esp32_ble_server in the firmware).
# Every characteristic except `battery_name` carries a little-endian IEEE-754
# float32 (ESPHome ByteBuffer.wrap(float)). `battery_name` is a UTF-8 string.
CHARACTERISTICS: dict[str, str] = {
    "voltage": "7aab0002-7aab-4535-af3e-ee76a35cc42d",
    "current": "7aab0003-7aab-4535-af3e-ee76a35cc42d",
    "power": "7aab0004-7aab-4535-af3e-ee76a35cc42d",
    "soc": "7aab0005-7aab-4535-af3e-ee76a35cc42d",
    "soh": "7aab0006-7aab-4535-af3e-ee76a35cc42d",
    "temperature": "7aab0007-7aab-4535-af3e-ee76a35cc42d",
    "charge_voltage_limit": "7aab0008-7aab-4535-af3e-ee76a35cc42d",
    "charge_current_limit": "7aab0009-7aab-4535-af3e-ee76a35cc42d",
    "discharge_current_limit": "7aab000a-7aab-4535-af3e-ee76a35cc42d",
    "discharge_voltage_limit": "7aab000b-7aab-4535-af3e-ee76a35cc42d",
    "remaining_capacity": "7aab000c-7aab-4535-af3e-ee76a35cc42d",
    "charging_power": "7aab000d-7aab-4535-af3e-ee76a35cc42d",
    "discharging_power": "7aab000e-7aab-4535-af3e-ee76a35cc42d",
    "battery_name": "7aab000f-7aab-4535-af3e-ee76a35cc42d",
}

STRING_KEYS: frozenset[str] = frozenset({"battery_name"})

# The firmware computes kWh as Ah * 51.2 V; keep the same nominal voltage.
NOMINAL_VOLTAGE = 51.2

# Reconnect back-off (seconds) and the silence timeout after which a link is
# considered dead. The firmware notifies every 5 s.
RECONNECT_MIN_DELAY = 5
RECONNECT_MAX_DELAY = 30
STALE_TIMEOUT = 60
CONNECT_TIMEOUT = 30
