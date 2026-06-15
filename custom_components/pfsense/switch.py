"""pfSense integration."""

import logging

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
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
    """Set up the pfSense switches."""

    @callback
    def process_entities_callback(hass, config_entry):
        data = hass.data[DOMAIN][config_entry.entry_id]
        coordinator = data[COORDINATOR]
        state = coordinator.data
        if not state:
            return []

        entities = []

        # New: pfBlockerNG Switch BY TranQuiL aka Malosaaaa
        if dict_get(state, "telemetry.pfblockerng") is not None:
            entity = PfSensePfBlockerNGSwitch(
                config_entry,
                coordinator,
                SwitchEntityDescription(
                    key="pfblockerng.enable",
                    name="pfBlockerNG AdBlocker",
                    icon="mdi:shield-half-full",
                    device_class=SwitchDeviceClass.SWITCH,
                ),
            )
            entities.append(entity)

        # filter rules
        if "filter" in state["config"].keys():
            rules = dict_get(state, "config.filter.rule")
            if isinstance(rules, list):
                for rule in rules:
                    if not isinstance(rule, dict):
                        continue
                    if "tracker" not in rule.keys() or "associated-rule-id" in rule.keys():
                        continue
                    if rule.get("descr") == "Anti-Lockout Rule" or not rule.get("tracker"):
                        continue

                    entity = PfSenseFilterSwitch(
                        config_entry,
                        coordinator,
                        SwitchEntityDescription(
                            key=f"filter.{rule['tracker']}",
                            name=f"Filter Rule {rule['tracker']} ({rule.get('descr', '')})",
                            icon="mdi:security-network",
                            device_class=SwitchDeviceClass.SWITCH,
                            entity_registry_enabled_default=False,
                        ),
                    )
                    entities.append(entity)

        # nat port forward rules
        if "nat" in state["config"].keys():
            rules = dict_get(state, "config.nat.rule")
            if isinstance(rules, list):
                for rule in rules:
                    if not isinstance(rule, dict):
                        continue
                    tracker = dict_get(rule, "created.time")
                    if not tracker:
                        continue

                    entity = PfSenseNatSwitch(
                        config_entry,
                        coordinator,
                        SwitchEntityDescription(
                            key=f"nat_port_forward.{tracker}",
                            name=f"NAT Port Forward {tracker} ({rule.get('descr', '')})",
                            icon="mdi:network",
                            device_class=SwitchDeviceClass.SWITCH,
                            entity_registry_enabled_default=False,
                        ),
                    )
                    entities.append(entity)

        # services
        for service in state.get("services", []):
            icon = "mdi:application-cog-outline"
            
            if service["name"] == "openvpn":
                key = f"service.{service['name']}-{service['vpnid']}.status"
                name = f"Service {service['name']} {service.get('description', '')} status"
            else:
                key = f"service.{service['name']}.status"
                name = f"Service {service['name']} status"

            entity = PfSenseServiceSwitch(
                config_entry,
                coordinator,
                SwitchEntityDescription(
                    key=key,
                    name=name,
                    icon=icon,
                    device_class=SwitchDeviceClass.SWITCH,
                    entity_registry_enabled_default=False,
                ),
            )
            entities.append(entity)

        return entities

    cem = CoordinatorEntityManager(
        hass,
        hass.data[DOMAIN][config_entry.entry_id][COORDINATOR],
        config_entry,
        process_entities_callback,
        async_add_entities,
    )
    cem.process_entities()


class PfSenseSwitch(PfSenseEntity, SwitchEntity):
    def __init__(
        self,
        config_entry,
        coordinator: DataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
    ) -> None:
        self.config_entry = config_entry
        self.entity_description = entity_description
        self.coordinator = coordinator
        self._attr_name = f"{self.pfsense_device_name} {entity_description.name}"
        self._attr_unique_id = slugify(
            f"{self.pfsense_device_unique_id}_{entity_description.key}"
        )

    @property
    def is_on(self):
        return False

    @property
    def extra_state_attributes(self):
        return None

# New: pfBlockerNG Switch Class BY TranQuiL aka Malosaaaa
class PfSensePfBlockerNGSwitch(PfSenseSwitch):
    @property
    def available(self) -> bool:
        state = self.coordinator.data
        if not state: return False
        return dict_get(state, "telemetry.pfblockerng") is not None and super().available

    @property
    def is_on(self):
        state = self.coordinator.data
        return dict_get(state, "telemetry.pfblockerng.enabled", False)

    async def async_turn_on(self, **kwargs):
        client = self._get_pfsense_client()
        await self.hass.async_add_executor_job(client.enable_pfblockerng)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        client = self._get_pfsense_client()
        await self.hass.async_add_executor_job(client.disable_pfblockerng)
        await self.coordinator.async_request_refresh()


class PfSenseFilterSwitch(PfSenseSwitch):
    def _pfsense_get_tracker(self):
        return self.entity_description.key.split(".")[1]

    def _pfsense_get_rule(self):
        state = self.coordinator.data
        if not state: return None
        tracker = self._pfsense_get_tracker()
        for rule in dict_get(state, "config.filter.rule", []):
            if rule.get("tracker") == tracker:
                return rule
        return None

    @property
    def available(self) -> bool:
        return self._pfsense_get_rule() is not None and super().available

    @property
    def is_on(self):
        rule = self._pfsense_get_rule()
        if rule is None:
            return STATE_UNKNOWN
        return "disabled" not in rule.keys()

    async def async_turn_on(self, **kwargs):
        rule = self._pfsense_get_rule()
        if rule is None: return
        client = self._get_pfsense_client()
        await self.hass.async_add_executor_job(
            client.enable_filter_rule_by_tracker, self._pfsense_get_tracker()
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        rule = self._pfsense_get_rule()
        if rule is None: return
        client = self._get_pfsense_client()
        await self.hass.async_add_executor_job(
            client.disable_filter_rule_by_tracker, self._pfsense_get_tracker()
        )
        await self.coordinator.async_request_refresh()


class PfSenseNatSwitch(PfSenseSwitch):
    def _pfsense_get_rule_type(self):
        return self.entity_description.key.split(".")[0]

    def _pfsense_get_tracker(self):
        return self.entity_description.key.split(".")[1]

    def _pfsense_get_rule(self):
        state = self.coordinator.data
        if not state: return None
        tracker = self._pfsense_get_tracker()
        rule_type = self._pfsense_get_rule_type()
        
        rules = []
        if rule_type == "nat_port_forward":
            rules = dict_get(state, "config.nat.rule", [])
        if rule_type == "nat_outbound":
            rules = dict_get(state, "config.nat.outbound.rule", [])

        for rule in rules:
            if dict_get(rule, "created.time") == tracker:
                return rule
        return None

    @property
    def available(self) -> bool:
        return self._pfsense_get_rule() is not None and super().available

    @property
    def is_on(self):
        rule = self._pfsense_get_rule()
        if rule is None:
            return STATE_UNKNOWN
        return "disabled" not in rule.keys()

    async def async_turn_on(self, **kwargs):
        rule = self._pfsense_get_rule()
        if rule is None: return
        client = self._get_pfsense_client()
        rule_type = self._pfsense_get_rule_type()
        
        method = client.enable_nat_port_forward_rule_by_created_time if rule_type == "nat_port_forward" else client.enable_nat_outbound_rule_by_created_time
        await self.hass.async_add_executor_job(method, self._pfsense_get_tracker())
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        rule = self._pfsense_get_rule()
        if rule is None: return
        client = self._get_pfsense_client()
        rule_type = self._pfsense_get_rule_type()
        
        method = client.disable_nat_port_forward_rule_by_created_time if rule_type == "nat_port_forward" else client.disable_nat_outbound_rule_by_created_time
        await self.hass.async_add_executor_job(method, self._pfsense_get_tracker())
        await self.coordinator.async_request_refresh()


class PfSenseServiceSwitch(PfSenseSwitch):
    def _pfsense_get_property_name(self):
        return self.entity_description.key.split(".")[2]

    def _pfsense_get_service_name(self):
        return self.entity_description.key.split(".")[1]

    def _pfsense_get_service(self):
        state = self.coordinator.data
        if not state: return None
        service_name = self._pfsense_get_service_name()
        
        for service in state.get("services", []):
            if service_name.startswith("openvpn"):
                parts = service_name.split("-")
                if service["name"] == parts[0] and str(service.get("vpnid")) == parts[1]:
                    return service
            elif service["name"] == service_name:
                return service
        return None

    @property
    def available(self) -> bool:
        service = self._pfsense_get_service()
        property_name = self._pfsense_get_property_name()
        return service is not None and property_name in service and super().available

    @property
    def is_on(self):
        service = self._pfsense_get_service()
        return service.get(self._pfsense_get_property_name(), STATE_UNKNOWN) if service else STATE_UNKNOWN

    async def async_turn_on(self, **kwargs):
        service = self._pfsense_get_service()
        if not service: return
        client = self._get_pfsense_client()
        await self.hass.async_add_executor_job(
            client.start_service, service["name"], service
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        service = self._pfsense_get_service()
        if not service: return
        client = self._get_pfsense_client()
        await self.hass.async_add_executor_job(
            client.stop_service, service["name"], service
        )
        await self.coordinator.async_request_refresh()