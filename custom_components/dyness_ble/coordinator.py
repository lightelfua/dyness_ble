"""Push-style BLE coordinator for the Dyness CAN BLE gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
import logging
import math
import struct
import time
from typing import TYPE_CHECKING, Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakNotFoundError,
    establish_connection,
)

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CHARACTERISTICS,
    CONNECT_TIMEOUT,
    DOMAIN,
    RECONNECT_MAX_DELAY,
    RECONNECT_MIN_DELAY,
    STALE_TIMEOUT,
    STRING_KEYS,
)

if TYPE_CHECKING:
    from . import DynessBLEConfigEntry

_LOGGER = logging.getLogger(__name__)


def parse_value(key: str, data: bytes | bytearray) -> float | str | None:
    """Decode a characteristic payload. Returns None for NaN/empty/garbage."""
    if key in STRING_KEYS:
        text = bytes(data).decode("utf-8", errors="ignore").replace("\x00", "")
        return text.strip() or None

    if len(data) < 4:
        return None
    (value,) = struct.unpack("<f", bytes(data[:4]))
    if math.isnan(value) or math.isinf(value):
        return None
    return value


class DynessBLECoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Keeps one GATT connection open and pushes notifications to entities."""

    config_entry: DynessBLEConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: DynessBLEConfigEntry, address: str
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {address}",
            update_interval=None,
        )
        self.address = address
        self.data = {}
        self.connected = False
        self._task: asyncio.Task[None] | None = None
        self._last_notify = 0.0
        self._last_error: str | None = None

    # ------------------------------------------------------------------ API

    async def _async_update_data(self) -> dict[str, Any]:
        """Data is pushed; a manual refresh just returns what we have."""
        return self.data

    @callback
    def async_start(self) -> None:
        """Start the background connection loop."""
        if self._task is None:
            self._task = self.config_entry.async_create_background_task(
                self.hass, self._async_run(), name=f"{DOMAIN} {self.address}"
            )

    async def async_shutdown(self) -> None:
        """Stop the loop and drop the BLE link."""
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await super().async_shutdown()

    # ------------------------------------------------------------ internals

    @callback
    def _set_connected(self, connected: bool) -> None:
        if self.connected != connected:
            self.connected = connected
            self.async_update_listeners()

    @callback
    def _handle_payload(self, key: str, payload: bytes | bytearray) -> None:
        self._last_notify = time.monotonic()
        value = parse_value(key, payload)
        if self.data.get(key) == value and key in self.data:
            return
        self.async_set_updated_data({**self.data, key: value})

    async def _async_run(self) -> None:
        """Connect, listen, reconnect forever."""
        delay = RECONNECT_MIN_DELAY
        while True:
            try:
                await self._async_session()
                delay = RECONNECT_MIN_DELAY
            except asyncio.CancelledError:
                raise
            except (BleakNotFoundError, BleakError, TimeoutError, OSError) as err:
                # Warn once per distinct error, then fall back to debug.
                message = f"{type(err).__name__}: {err}"
                level = logging.DEBUG if message == self._last_error else logging.WARNING
                self._last_error = message
                _LOGGER.log(level, "%s: cannot connect: %s", self.address, message)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("%s: unexpected error", self.address)
            finally:
                self._set_connected(False)

            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_DELAY)

    async def _async_session(self) -> None:
        """One connected session. Returns when the link drops or goes stale."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise BleakNotFoundError(f"{self.address} is not in range")

        disconnected = asyncio.Event()
        loop = self.hass.loop

        def _on_disconnect(_client: BleakClient) -> None:
            loop.call_soon_threadsafe(disconnected.set)

        def _refresh_device():
            return (
                bluetooth.async_ble_device_from_address(
                    self.hass, self.address, connectable=True
                )
                or ble_device
            )

        client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            self.name,
            disconnected_callback=_on_disconnect,
            ble_device_callback=_refresh_device,
            timeout=CONNECT_TIMEOUT,
        )
        try:
            present = [
                (key, uuid)
                for key, uuid in CHARACTERISTICS.items()
                if client.services.get_characteristic(uuid) is not None
            ]
            missing = set(CHARACTERISTICS) - {key for key, _ in present}
            if missing:
                _LOGGER.warning(
                    "%s: characteristics missing in firmware: %s",
                    self.address,
                    ", ".join(sorted(missing)),
                )
            if not present:
                raise BleakError("device exposes none of the expected characteristics")

            # Characteristics whose notify can't be enabled are polled instead.
            polled: list[tuple[str, str]] = []
            for key, uuid in present:
                try:
                    await client.start_notify(uuid, self._make_notify_cb(key))
                except (BleakError, TimeoutError, OSError, ValueError) as err:
                    _LOGGER.warning(
                        "%s: notify unavailable for %s (%s), polling instead",
                        self.address,
                        key,
                        err,
                    )
                    polled.append((key, uuid))

            self._last_notify = time.monotonic()
            self._last_error = None
            self._set_connected(True)
            _LOGGER.debug("%s: connected, %d characteristics", self.address, len(present))

            # Prime the entities right away instead of waiting for the 5 s tick.
            for key, uuid in present:
                try:
                    payload = await client.read_gatt_char(uuid)
                except BleakError as err:
                    _LOGGER.debug("%s: read %s failed: %s", self.address, key, err)
                    continue
                self._handle_payload(key, payload)

            wait = 5 if polled else STALE_TIMEOUT / 2
            while not disconnected.is_set():
                with suppress(TimeoutError):
                    await asyncio.wait_for(disconnected.wait(), timeout=wait)
                if disconnected.is_set():
                    break
                for key, uuid in polled:
                    try:
                        self._handle_payload(key, await client.read_gatt_char(uuid))
                    except BleakError as err:
                        _LOGGER.debug("%s: poll %s failed: %s", self.address, key, err)
                if time.monotonic() - self._last_notify > STALE_TIMEOUT:
                    _LOGGER.debug("%s: no notifications, reconnecting", self.address)
                    break
        finally:
            with suppress(Exception):
                await client.disconnect()

    def _make_notify_cb(self, key: str) -> Callable[[Any, bytearray], None]:
        def _cb(_char: Any, payload: bytearray) -> None:
            self.hass.loop.call_soon_threadsafe(self._handle_payload, key, bytes(payload))

        return _cb
