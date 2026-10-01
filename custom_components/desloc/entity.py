"""Shared device identity and availability."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, TESTED_MODELS
from .coordinator import DeslocCoordinator


class DeslocEntity(CoordinatorEntity[DeslocCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: DeslocCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_{key}"
        device = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.mac)}, manufacturer="DESLOC",
            name=device.name if device else "DESLOC lock",
            model=device.model if device else None,
            sw_version=device.firmware if device else None,
        )

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Discovery alone does not establish another model's compatibility."""
        device = self.coordinator.data
        model = device.model if device else self._attr_device_info.get("model")
        return {"model_validation": "tested" if model in TESTED_MODELS else "experimental"}

    @property
    def available(self) -> bool:
        # Cloud reachability only; onlineStatus enum is not yet verified.
        return super().available and self.coordinator.data is not None
