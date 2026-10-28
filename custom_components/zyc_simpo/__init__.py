"""The ZYC Simpo 5000 integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import ZycCoordinator
from .zyc import ZycClient

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

# ConfigEntry carrying the coordinator in .runtime_data (HA 2024.5+).
ZycConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: ZycConfigEntry) -> bool:
    """Set up ZYC Simpo from a config entry."""
    client = ZycClient(entry.data[CONF_HOST])
    coordinator = ZycCoordinator(hass, entry, client)
    # Re-discovers the modules present right now, so a bank that grew or
    # shrank since last start comes up correctly.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    return True


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
    delete the whole-bank device or a module that is still reporting.
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
            return False  # module still present
    return True
