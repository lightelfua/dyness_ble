"""Config flow for the Dyness CAN BLE integration."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, LOCAL_NAME_PREFIX, SERVICE_UUID

MAC_RE = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")


def _is_ours(info: BluetoothServiceInfoBleak) -> bool:
    return SERVICE_UUID in info.service_uuids or (info.name or "").startswith(
        LOCAL_NAME_PREFIX
    )


class DynessBLEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dyness CAN BLE."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    # ----------------------------------------------------------- bluetooth

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle automatic discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered device."""
        assert self._discovery_info is not None
        title = self._discovery_info.name or self._discovery_info.address
        if user_input is not None:
            return self.async_create_entry(
                title=title, data={CONF_ADDRESS: self._discovery_info.address}
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": title},
        )

    # ---------------------------------------------------------------- user

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick one of the devices seen by Home Assistant's Bluetooth stack."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            info = self._discovered[address]
            return self.async_create_entry(
                title=info.name or address, data={CONF_ADDRESS: address}
            )

        configured = self._async_current_ids()
        self._discovered = {
            info.address: info
            for info in bluetooth.async_discovered_service_info(self.hass, True)
            if info.address not in configured and _is_ours(info)
        }
        if not self._discovered:
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: f"{info.name or 'Dyness CAN BLE'} ({address})"
                            for address, info in self._discovered.items()
                        }
                    )
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter a MAC address by hand."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper().replace("-", ":")
            if not MAC_RE.match(address):
                errors[CONF_ADDRESS] = "invalid_address"
            elif (
                bluetooth.async_ble_device_from_address(
                    self.hass, address, connectable=True
                )
                is None
            ):
                errors[CONF_ADDRESS] = "not_found"
            else:
                await self.async_set_unique_id(address, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Dyness CAN BLE {address[-5:]}",
                    data={CONF_ADDRESS: address},
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
            errors=errors,
        )
