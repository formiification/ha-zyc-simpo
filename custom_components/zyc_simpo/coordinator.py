"""Data update coordinator for the ZYC Simpo integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .zyc import ZycClient, ZycError

_LOGGER = logging.getLogger(__name__)


class ZycCoordinator(DataUpdateCoordinator[dict]):
    """Polls the dongle and shares decoded telemetry with the sensors."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: ZycClient) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.entry = entry
        self.client = client
        # Re-discovered on every setup (startup / reload), so adding or
        # removing battery modules is picked up without breaking the entry.
        self.addrs: list[int] | None = None

    async def _async_update_data(self) -> dict:
        return await self.hass.async_add_executor_job(self._poll)

    def _poll(self) -> dict:
        try:
            if self.addrs is None:
                self.addrs = self.client.discover()
                _LOGGER.info("Discovered %d ZYC battery modules", len(self.addrs))
            return self.client.poll(self.addrs)
        except ZycError as err:
            raise UpdateFailed(str(err)) from err
