"""Binary sensors (BMS warnings) for the ZYC Simpo integration.

The warnings are derived from the confirmed telemetry (voltage / current /
temperature) against safe LiFePO4 thresholds — they are not the BMS's own
protection-flag registers, whose bit layout is undocumented. Each sensor lists
the active warnings in its attributes.
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ZycConfigEntry
from .const import (
    DOMAIN,
    MANUFACTURER,
    MODEL,
    WARN_CELL_IMBALANCE_MV,
    WARN_CURRENT_HIGH,
    WARN_TEMP_HIGH,
    WARN_TEMP_LOW_CHARGE,
    WARN_VOLT_HIGH,
    WARN_VOLT_LOW,
)
from .coordinator import ZycCoordinator


def module_warnings(m: dict) -> list[str]:
    """Return the list of active warnings for one module's telemetry."""
    warnings: list[str] = []
    v = m.get("voltage_v")
    i = m.get("current_a")
    t = m.get("temp_c")
    if v is not None and v >= WARN_VOLT_HIGH:
        warnings.append("overvoltage")
    if v is not None and v <= WARN_VOLT_LOW:
        warnings.append("undervoltage")
    if t is not None and t >= WARN_TEMP_HIGH:
        warnings.append("overtemperature")
    if t is not None and i is not None and i > 0 and t <= WARN_TEMP_LOW_CHARGE:
        warnings.append("charge_under_temperature")
    if i is not None and abs(i) >= WARN_CURRENT_HIGH:
        warnings.append("overcurrent")
    delta = m.get("cell_v_delta")
    if delta is not None and delta >= WARN_CELL_IMBALANCE_MV:
        warnings.append("cell_imbalance")
    return warnings


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZycConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BMS warning binary sensors."""
    coordinator = entry.runtime_data
    # One warning sensor per known module (persisted set), so a briefly offline
    # module keeps its entity instead of being dropped.
    entities: list[BinarySensorEntity] = [
        ZycModuleProblem(coordinator, entry, addr, {"serial": serial})
        for addr, serial in sorted(coordinator.known.items())
    ]
    entities.append(ZycBankProblem(coordinator, entry))
    async_add_entities(entities)


class ZycModuleProblem(CoordinatorEntity[ZycCoordinator], BinarySensorEntity):
    """BMS warning state for a single module."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "bms_warning"

    def __init__(
        self,
        coordinator: ZycCoordinator,
        entry: ZycConfigEntry,
        addr: int,
        module: dict,
    ) -> None:
        super().__init__(coordinator)
        self._addr = addr
        serial = module.get("serial") or f"{entry.entry_id}_mod{addr}"
        self._attr_unique_id = f"{serial}_bms_warning"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=f"ZYC Module {addr}",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        return super().available and self._addr in self.coordinator.data["modules"]

    @property
    def is_on(self) -> bool | None:
        module = self.coordinator.data["modules"].get(self._addr)
        if module is None:
            return None
        return bool(module_warnings(module))

    @property
    def extra_state_attributes(self) -> dict:
        module = self.coordinator.data["modules"].get(self._addr)
        return {"warnings": module_warnings(module) if module else []}


class ZycBankProblem(CoordinatorEntity[ZycCoordinator], BinarySensorEntity):
    """True if any module reports a warning."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "bms_warning_any"

    def __init__(self, coordinator: ZycCoordinator, entry: ZycConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_bms_warning_any"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="ZYC Simpo Bank",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def is_on(self) -> bool:
        return any(
            module_warnings(m) for m in self.coordinator.data["modules"].values()
        )

    @property
    def extra_state_attributes(self) -> dict:
        offending = {
            addr: module_warnings(m)
            for addr, m in self.coordinator.data["modules"].items()
            if module_warnings(m)
        }
        return {"modules_with_warnings": offending}
