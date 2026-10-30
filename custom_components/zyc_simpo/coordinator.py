"""Data update coordinator for the ZYC Simpo integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PRUNE_AFTER_MISSED_SCANS,
    REDISCOVER_EVERY,
)
from .zyc import ZycClient, ZycError

_LOGGER = logging.getLogger(__name__)


class ZycCoordinator(DataUpdateCoordinator[dict]):
    """Polls the dongle and shares decoded telemetry with the sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: ZycClient,
        known: dict[int, str],
        store: Store,
    ) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.entry = entry
        self.client = client
        self._store = store
        # Known module set {addr: serial}, persisted across restarts. A module
        # that is briefly offline (even over a restart) keeps its entities and
        # recovers on its own, instead of being dropped and orphaned. The set
        # only grows automatically; a module is removed only when the user
        # deletes its device.
        self.known: dict[int, str] = dict(known)
        for addr, serial in self.known.items():
            if serial:
                client.seed_serial(addr, serial)
        # Consecutive successful re-scans each known module has been missing;
        # used to prune a module that was physically removed (see _poll).
        self._absent: dict[int, int] = {}
        # Force a discovery on the first poll of the session (catches a bank
        # that grew while HA was off), then re-scan periodically.
        self._polls_since_scan = REDISCOVER_EVERY
        self._known_dirty = False
        self._reload_needed = False

    async def _async_update_data(self) -> dict:
        self._known_dirty = False
        self._reload_needed = False
        data = await self.hass.async_add_executor_job(self._poll)
        # hass/entry mutations must happen on the event loop, not in the executor.
        if self._known_dirty:
            await self._store.async_save(
                {str(a): s for a, s in self.known.items()}
            )
        if self._reload_needed:
            self.hass.config_entries.async_schedule_reload(self.entry.entry_id)
        return data

    def _poll(self) -> dict:
        try:
            discovered: list[int] | None = None
            if not self.known or self._polls_since_scan >= REDISCOVER_EVERY:
                self._polls_since_scan = 0
                try:
                    discovered = self.client.discover()
                except ZycError:
                    # Dongle momentarily unreachable for a scan; fall back to
                    # polling the modules we already know about.
                    discovered = None
            else:
                self._polls_since_scan += 1

            if discovered:
                # A successful scan: reconcile the known set with what is there.
                serials = self.client.serials()
                before = set(self.known)
                # Add any newly seen modules.
                for a in discovered:
                    self.known[a] = serials.get(a) or self.known.get(a)
                # Track sustained absence; prune a module only after it has been
                # missing from several consecutive successful scans (physically
                # removed, not just briefly offline). A pruned module that comes
                # back is simply re-added on a later scan.
                for a in list(self.known):
                    if a in discovered:
                        self._absent.pop(a, None)
                    else:
                        self._absent[a] = self._absent.get(a, 0) + 1
                        if self._absent[a] >= PRUNE_AFTER_MISSED_SCANS:
                            self.known.pop(a, None)
                            self._absent.pop(a, None)
                if set(self.known) != before:
                    self._known_dirty = True
                    _LOGGER.info("ZYC known modules: %s", sorted(self.known))
                    # The entity set changed; entities are (re)created on setup,
                    # so reload — except on the very first poll, where setup is
                    # about to create them anyway.
                    if self.data is not None:
                        self._reload_needed = True

            addrs = sorted(self.known) if self.known else (discovered or [])
            if not addrs:
                raise ZycError("no battery modules responded")
            return self.client.poll(addrs)
        except ZycError as err:
            raise UpdateFailed(str(err)) from err

    async def async_forget_module(self, serial: str) -> None:
        """Drop a module from the known set so a deleted device is not recreated."""
        removed = [a for a, s in self.known.items() if s == serial]
        for addr in removed:
            self.known.pop(addr, None)
        if removed:
            await self._store.async_save(
                {str(a): s for a, s in self.known.items()}
            )
