"""Sensor platform for the ZYC Simpo integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    RestoreSensor,
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import ZycConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import ZycCoordinator

UNIT_AMPERE_HOUR = "Ah"


@dataclass(frozen=True, kw_only=True)
class ZycSensorDescription(SensorEntityDescription):
    """Describes a ZYC sensor and how to read its value from a data dict."""

    value_fn: Callable[[dict], float | int | None]


MODULE_SENSORS: tuple[ZycSensorDescription, ...] = (
    ZycSensorDescription(
        key="voltage_v",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["voltage_v"],
    ),
    ZycSensorDescription(
        key="current_a",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["current_a"],
    ),
    ZycSensorDescription(
        key="power_w",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["power_w"],
    ),
    ZycSensorDescription(
        key="temp_c",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["temp_c"],
    ),
    ZycSensorDescription(
        key="soc_pct",
        translation_key="soc",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["soc_pct"],
    ),
    ZycSensorDescription(
        key="soh_pct",
        translation_key="soh",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["soh_pct"],
    ),
    ZycSensorDescription(
        key="cell_v_delta",
        translation_key="cell_delta",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["cell_v_delta"],
    ),
    ZycSensorDescription(
        key="cell_v_max",
        translation_key="cell_max",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["cell_v_max"],
    ),
    ZycSensorDescription(
        key="cell_v_min",
        translation_key="cell_min",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["cell_v_min"],
    ),
    ZycSensorDescription(
        key="charge_voltage_limit_v",
        translation_key="charge_voltage_limit",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["charge_voltage_limit_v"],
    ),
    ZycSensorDescription(
        key="charge_current_limit_a",
        translation_key="charge_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["charge_current_limit_a"],
    ),
    ZycSensorDescription(
        key="discharge_voltage_limit_v",
        translation_key="discharge_voltage_limit",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["discharge_voltage_limit_v"],
    ),
    ZycSensorDescription(
        key="discharge_current_limit_a",
        translation_key="discharge_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["discharge_current_limit_a"],
    ),
    ZycSensorDescription(
        key="remaining_ah",
        translation_key="remaining_ah",
        native_unit_of_measurement=UNIT_AMPERE_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["remaining_ah"],
    ),
    ZycSensorDescription(
        key="full_ah",
        translation_key="full_ah",
        native_unit_of_measurement=UNIT_AMPERE_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["full_ah"],
    ),
    ZycSensorDescription(
        key="firmware",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("firmware"),
    ),
)

AGGREGATE_SENSORS: tuple[ZycSensorDescription, ...] = (
    ZycSensorDescription(
        key="current_a_sum",
        translation_key="current_total",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["current_a_sum"],
    ),
    ZycSensorDescription(
        key="power_w_sum",
        translation_key="power_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["power_w_sum"],
    ),
    ZycSensorDescription(
        key="voltage_v_avg",
        translation_key="voltage_avg",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["voltage_v_avg"],
    ),
    ZycSensorDescription(
        key="temp_c_avg",
        translation_key="temperature_avg",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["temp_c_avg"],
    ),
    ZycSensorDescription(
        key="soc_pct_avg",
        translation_key="soc_avg",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["soc_pct_avg"],
    ),
    ZycSensorDescription(
        key="soh_pct_avg",
        translation_key="soh_avg",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["soh_pct_avg"],
    ),
    ZycSensorDescription(
        key="soh_pct_min",
        translation_key="soh_min",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["soh_pct_min"],
    ),
    ZycSensorDescription(
        key="cell_v_delta",
        translation_key="cell_delta_bank",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["cell_v_delta"],
    ),
    ZycSensorDescription(
        key="remaining_ah_sum",
        translation_key="remaining_ah_total",
        native_unit_of_measurement=UNIT_AMPERE_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["remaining_ah_sum"],
    ),
    ZycSensorDescription(
        key="full_ah_sum",
        translation_key="full_ah_total",
        native_unit_of_measurement=UNIT_AMPERE_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["full_ah_sum"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZycConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ZYC sensors from a config entry."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = []
    # Build entities for every known module (persisted set), not just the ones
    # responding right now, so a briefly offline module keeps its entities and
    # recovers instead of being dropped as "no longer provided".
    for addr, serial in sorted(coordinator.known.items()):
        module = {"serial": serial}
        for desc in MODULE_SENSORS:
            entities.append(ZycModuleSensor(coordinator, entry, addr, module, desc))
        for cell in range(16):
            entities.append(ZycCellSensor(coordinator, entry, addr, module, cell))
    for desc in AGGREGATE_SENSORS:
        entities.append(ZycAggregateSensor(coordinator, entry, desc))

    entities.append(ZycEnergySensor(coordinator, entry, "charge"))
    entities.append(ZycEnergySensor(coordinator, entry, "discharge"))

    async_add_entities(entities)


class ZycBaseSensor(CoordinatorEntity[ZycCoordinator], SensorEntity):
    """Common bits for ZYC sensors."""

    entity_description: ZycSensorDescription
    _attr_has_entity_name = True


class ZycModuleSensor(ZycBaseSensor):
    """A sensor for a single battery module."""

    def __init__(
        self,
        coordinator: ZycCoordinator,
        entry: ZycConfigEntry,
        addr: int,
        module: dict,
        description: ZycSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._addr = addr
        self.entity_description = description
        serial = module.get("serial") or f"{entry.entry_id}_mod{addr}"
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=f"ZYC Module {addr}",
            manufacturer=MANUFACTURER,
            model=MODEL,
            serial_number=module.get("serial"),
            sw_version=module.get("firmware"),
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._addr in self.coordinator.data["modules"]
        )

    @property
    def native_value(self) -> float | int | None:
        module = self.coordinator.data["modules"].get(self._addr)
        if module is None:
            return None
        return self.entity_description.value_fn(module)


class ZycCellSensor(CoordinatorEntity[ZycCoordinator], SensorEntity):
    """Voltage of one individual cell within a module (diagnostic, mV)."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: ZycCoordinator,
        entry: ZycConfigEntry,
        addr: int,
        module: dict,
        cell: int,
    ) -> None:
        super().__init__(coordinator)
        self._addr = addr
        self._cell = cell  # 0-based index
        serial = module.get("serial") or f"{entry.entry_id}_mod{addr}"
        self._attr_unique_id = f"{serial}_cell_{cell + 1}"
        self._attr_name = f"Cell {cell + 1}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=f"ZYC Module {addr}",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        module = self.coordinator.data["modules"].get(self._addr)
        return (
            super().available
            and module is not None
            and len(module.get("cells", [])) > self._cell
        )

    @property
    def native_value(self) -> int | None:
        module = self.coordinator.data["modules"].get(self._addr)
        if module is None:
            return None
        cells = module.get("cells")
        if not cells or self._cell >= len(cells):
            return None
        return cells[self._cell]


class ZycAggregateSensor(ZycBaseSensor):
    """A whole-bank aggregate sensor (summed or averaged)."""

    def __init__(
        self,
        coordinator: ZycCoordinator,
        entry: ZycConfigEntry,
        description: ZycSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="ZYC Simpo Bank",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def native_value(self) -> float | int | None:
        return self.entity_description.value_fn(self.coordinator.data["aggregate"])


# Skip integration across a gap longer than this (e.g. HA was down), so a
# downtime does not dump a huge lump of energy into the running total.
MAX_INTEGRATION_GAP = 7200  # seconds


class ZycEnergySensor(CoordinatorEntity[ZycCoordinator], RestoreSensor):
    """Cumulative charged/discharged energy, integrated from total power.

    Feeds the HA Energy dashboard (battery in / out). The running total is
    restored across restarts so it keeps counting monotonically.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3

    def __init__(
        self, coordinator: ZycCoordinator, entry: ZycConfigEntry, direction: str
    ) -> None:
        super().__init__(coordinator)
        self._direction = direction  # "charge" (power > 0) or "discharge"
        self._attr_translation_key = f"energy_{direction}d"
        self._attr_unique_id = f"{entry.entry_id}_energy_{direction}d"
        self._total_kwh: float = 0.0
        self._last_ts = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="ZYC Simpo Bank",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and last.native_value is not None:
            try:
                self._total_kwh = float(last.native_value)
            except (TypeError, ValueError):
                self._total_kwh = 0.0
        self._attr_native_value = round(self._total_kwh, 3)
        self._last_ts = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        now = dt_util.utcnow()
        if self.coordinator.last_update_success and self._last_ts is not None:
            dt = (now - self._last_ts).total_seconds()
            if 0 < dt <= MAX_INTEGRATION_GAP:
                power_w = self.coordinator.data["aggregate"]["power_w_sum"]
                if self._direction == "charge" and power_w > 0:
                    self._total_kwh += power_w * dt / 3_600_000
                elif self._direction == "discharge" and power_w < 0:
                    self._total_kwh += -power_w * dt / 3_600_000
        self._last_ts = now
        self._attr_native_value = round(self._total_kwh, 3)
        super()._handle_coordinator_update()
