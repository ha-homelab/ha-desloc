"""Captured battery/RSSI and explicitly labelled raw protocol diagnostics."""
from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass,
)
from homeassistant.const import EntityCategory, PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeslocConfigEntry
from .entity import DeslocEntity

DESCRIPTIONS = (
    SensorEntityDescription(key="battery", name="Battery", device_class=SensorDeviceClass.BATTERY,
                            native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="rssi", name="Wi-Fi signal", device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
                            state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="door_state", name="Door state code", entity_category=EntityCategory.DIAGNOSTIC,
                            entity_registry_enabled_default=False),
    SensorEntityDescription(key="online_status", name="Online status code", entity_category=EntityCategory.DIAGNOSTIC,
                            entity_registry_enabled_default=False),
)


async def async_setup_entry(hass: HomeAssistant, entry: DeslocConfigEntry,
                           async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(DeslocSensor(entry.runtime_data, description) for description in DESCRIPTIONS)


class DeslocSensor(DeslocEntity, SensorEntity):
    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | None:
        device = self.coordinator.data
        return getattr(device, self.entity_description.key) if device else None
