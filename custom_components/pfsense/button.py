"""pfSense button platform."""
import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from . import CoordinatorEntityManager, PfSenseEntity
from .const import COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
):
    """Set up the pfSense buttons."""
    @callback
    def process_entities_callback(hass, config_entry):
        data = hass.data[DOMAIN][config_entry.entry_id]
        coordinator = data[COORDINATOR]
        
        entities = [
            PfSenseRebootButton(
                config_entry, coordinator,
                ButtonEntityDescription(key="system_reboot", name="Reboot Router", icon="mdi:restart")
            ),
            PfSenseHaltButton(
                config_entry, coordinator,
                ButtonEntityDescription(key="system_halt", name="Halt Router", icon="mdi:power")
            ),
            PfSenseResetStatesButton(
                config_entry, coordinator,
                ButtonEntityDescription(key="reset_states", name="Reset State Table", icon="mdi:delete-sweep")
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

class PfSenseButton(PfSenseEntity, ButtonEntity):
    """Base class for pfSense buttons."""
    def __init__(
        self, config_entry, coordinator: DataUpdateCoordinator, entity_description: ButtonEntityDescription
    ) -> None:
        self.config_entry = config_entry
        self.entity_description = entity_description
        self.coordinator = coordinator
        self._attr_name = f"{self.pfsense_device_name} {entity_description.name}"
        self._attr_unique_id = slugify(f"{self.pfsense_device_unique_id}_{entity_description.key}")

class PfSenseRebootButton(PfSenseButton):
    async def async_press(self) -> None:
        await self.hass.async_add_executor_job(self.service_system_reboot)

class PfSenseHaltButton(PfSenseButton):
    async def async_press(self) -> None:
        await self.hass.async_add_executor_job(self.service_system_halt)

class PfSenseResetStatesButton(PfSenseButton):
    async def async_press(self) -> None:
        await self.hass.async_add_executor_job(self.service_reset_state_table)