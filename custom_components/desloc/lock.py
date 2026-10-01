"""Lock entity using observed commands and reported bolt state."""
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeslocConfigEntry
from .entity import DeslocEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: DeslocConfigEntry,
                           async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([DeslocLock(entry.runtime_data, "lock")])


class DeslocLock(DeslocEntity, LockEntity):
    _attr_name = None

    @property
    def is_locked(self) -> bool | None:
        return self.coordinator.is_locked

    @property
    def is_locking(self) -> bool:
        return self.coordinator.pending_target is True

    @property
    def is_unlocking(self) -> bool:
        return self.coordinator.pending_target is False

    async def async_lock(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_locked(True)

    async def async_unlock(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_locked(False)
