"""pfSense integration binary sensors."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from . import CoordinatorEntityManager, PfSenseEntity, dict_get
from .const import COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
):
    """Set up the pfSense binary sensors."""

    @callback
    def process_entities_callback(hass, config_entry):
        data = hass.data[DOMAIN][config_entry.entry_id]
        coordinator = data[COORDINATOR]
        
        entities = [
            PfSenseCarpStatusBinarySensor(
                config_entry, coordinator,
                BinarySensorEntityDescription(key="carp.status", name="CARP Status", icon="mdi:server-network"),
                False,
            ),
            PfSensePendingNoticesPresentBinarySensor(
                config_entry, coordinator,
                BinarySensorEntityDescription(key="notices.pending", name="Pending Notices Present", icon="mdi:alert"),
                True,
            ),
            # New: smart overload sensors  by TranQuiL aka Malosaaaa
            PfSenseCpuOverloadBinarySensor(
                config_entry, coordinator,
                BinarySensorEntityDescription(key="cpu_overload", name="CPU Overload (>90%)", icon="mdi:cpu-64-bit", device_class=BinarySensorDeviceClass.PROBLEM),
                True,
            ),
            PfSenseMemoryOverloadBinarySensor(
                config_entry, coordinator,
                BinarySensorEntityDescription(key="memory_overload", name="Memory Overload (>90%)", icon="mdi:memory", device_class=BinarySensorDeviceClass.PROBLEM),
                True,
            ),
        ]
        return entities

    cem = CoordinatorEntityManager(
        hass,
        hass.data[DOMAIN][config_entry.entry_id][COORDINATOR],
        config_entry,
        process_entities_callback,
        async_add_entities,
    )
    cem.process_entities()

class PfSenseBinarySensor(PfSenseEntity, BinarySensorEntity):
    def __init__(
        self, config_entry, coordinator: DataUpdateCoordinator, entity_description: BinarySensorEntityDescription, enabled_default: bool
    ) -> None:
        self.config_entry = config_entry
        self.entity_description = entity_description
        self.coordinator = coordinator
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_name = f"{self.pfsense_device_name} {entity_description.name}"
        self._attr_unique_id = slugify(f"{self.pfsense_device_unique_id}_{entity_description.key}")

    @property
    def is_on(self):
        return False

class PfSenseCarpStatusBinarySensor(PfSenseBinarySensor):
    @property
    def is_on(self):
        return dict_get(self.coordinator.data, "carp_status", STATE_UNKNOWN)

class PfSensePendingNoticesPresentBinarySensor(PfSenseBinarySensor):
    @property
    def is_on(self):
        return dict_get(self.coordinator.data, "notices.pending_notices_present", STATE_UNKNOWN)

    @property
    def device_class(self):
        return BinarySensorDeviceClass.PROBLEM

    @property
    def extra_state_attributes(self):
        attrs = {}
        notices = dict_get(self.coordinator.data, "notices.pending_notices")
        if notices:
            attrs["pending_notices"] = notices
        return attrs

# new: CPU overload check by TranQuiL aka Malosaaa
class PfSenseCpuOverloadBinarySensor(PfSenseBinarySensor):
    @property
    def is_on(self):
        usage = dict_get(self.coordinator.data, "telemetry.cpu.used_percent", 0)
        return usage > 90

# new: memory overload check by TranQuiL aka Malosaaa
class PfSenseMemoryOverloadBinarySensor(PfSenseBinarySensor):
    @property
    def is_on(self):
        usage = dict_get(self.coordinator.data, "telemetry.memory.used_percent", 0)
        return usage > 90