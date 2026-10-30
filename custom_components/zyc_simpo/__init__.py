"""The ZYC Simpo 5000 integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION
from .coordinator import ZycCoordinator
from .zyc import ZycClient

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

# ConfigEntry carrying the coordinator in .runtime_data (HA 2024.5+).
ZycConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: ZycConfigEntry) -> bool:
    """Set up ZYC Simpo from a config entry."""
    client = ZycClient(entry.data[CONF_HOST])
    # The set of battery modules is remembered across restarts, so a module
    # that is briefly offline keeps its entities instead of being orphaned.
    store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
    stored = await store.async_load() or {}
    known = {int(addr): serial for addr, serial in stored.items()}
    coordinator = ZycCoordinator(hass, entry, client, known, store)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _cleanup_stale_devices(hass, entry, coordinator)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    return True


def _cleanup_stale_devices(
    hass: HomeAssistant, entry: ZycConfigEntry, coordinator: ZycCoordinator
) -> None:
    """Remove module devices that are no longer in the known set.

    Clears a physically removed (pruned) or user-deleted module cleanly, so no
    orphaned "no longer provided" entities are left behind. The bank device and
    every currently known module (even one briefly offline) are kept.
    """
    dev_reg = dr.async_get(hass)
    valid = {(DOMAIN, entry.entry_id)} | {
        (DOMAIN, serial) for serial in coordinator.known.values() if serial
    }
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if not device.identifiers & valid:
            dev_reg.async_remove_device(device.id)


async def async_unload_entry(hass: HomeAssistant, entry: ZycConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_reload_on_update(hass: HomeAssistant, entry: ZycConfigEntry) -> None:
    """Reload the entry when options change (applies the new scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ZycConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow deleting a battery module device only once it is gone.

    Lets the user clean up a removed/dead module from the UI, while refusing to
    delete the whole-bank device or a module that is still reporting. A deleted
    module is also forgotten from the persisted set so it is not recreated.
    """
    coordinator: ZycCoordinator = entry.runtime_data
    present = {
        m.get("serial") for m in coordinator.data["modules"].values() if m.get("serial")
    }
    for domain, ident in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        if ident == entry.entry_id:
            return False  # the aggregate bank device stays
        if ident in present:
            return False  # module still reporting — keep it
        await coordinator.async_forget_module(ident)
    return True
