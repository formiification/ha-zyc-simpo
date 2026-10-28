"""Config flow for the ZYC Simpo integration — asks for the dongle IP only."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .zyc import ZycClient, ZycError

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class ZycSimpoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZYC Simpo."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "ZycOptionsFlow":
        return ZycOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            client = ZycClient(host)
            try:
                addrs = await self.hass.async_add_executor_job(client.discover)
                data = await self.hass.async_add_executor_job(client.poll, addrs)
            except ZycError:
                errors["base"] = "cannot_connect"
            else:
                # one dongle per installation: key on the first module serial
                serial = next(iter(data["modules"].values())).get("serial") or host
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                count = data["aggregate"]["module_count"]
                return self.async_create_entry(
                    title=f"ZYC Simpo ({count} modules)",
                    data={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )


class ZycOptionsFlow(OptionsFlow):
    """Let the user change the polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    cv.positive_int,
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
