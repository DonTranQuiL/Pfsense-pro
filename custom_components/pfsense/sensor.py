"""Provides a sensor to track various status aspects of pfSense."""

import logging
import re

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify
from homeassistant.util.dt import utc_from_timestamp

from . import CoordinatorEntityManager, PfSenseEntity, dict_get
from .const import (
    COORDINATOR,
    COUNT,
    DATA_PACKETS,
    DATA_RATE_PACKETS_PER_SECOND,
    DOMAIN,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
):
    """Set up the pfSense sensors."""

    @callback
    def process_entities_callback(hass, config_entry):
        data = hass.data[DOMAIN][config_entry.entry_id]
        coordinator = data[COORDINATOR]
        state = coordinator.data
        if not state:
            return []
            
        resources = [sensor_id for sensor_id in SENSOR_TYPES]
        entities = []

        wan_ip_entity = PfSenseStaticKeySensor(
            config_entry,
            coordinator,
            SensorEntityDescription(
                key="telemetry.wan_ip",
                name="WAN IP Address",
                icon="mdi:web",
            ),
            True,
        )
        entities.append(wan_ip_entity)
        # add standard entities
        for sensor_type in resources:
            enabled_default = False
            if sensor_type in [
                "telemetry.pfstate.used_percent",
                "telemetry.mbuf.used_percent",
                "telemetry.memory.swap_used_percent",
                "telemetry.memory.used_percent",
                "telemetry.cpu.used_percent",
                "telemetry.cpu.frequency.current",
                "telemetry.system.load_average.one_minute",
                "telemetry.system.load_average.five_minute",
                "telemetry.system.load_average.fifteen_minute",
                "telemetry.system.temp",
                "telemetry.system.boottime",
                "dhcp_stats.leases.online",
            ]:
                enabled_default = True

            entity = PfSenseStaticKeySensor(
                config_entry,
                coordinator,
                SENSOR_TYPES[sensor_type],
                enabled_default,
            )
            entities.append(entity)

        # filesystems
        for filesystem in dict_get(state, "telemetry.filesystems", []):
            device_clean = normalize_filesystem_device_name(filesystem["device"])
            mountpoint_clean = normalize_filesystem_device_name(
                filesystem["mountpoint"]
            )
            entity = PfSenseFilesystemSensor(
                config_entry,
                coordinator,
                SensorEntityDescription(
                    key=f"telemetry.filesystems.{device_clean}",
                    name="Filesystem Used Percentage {}".format(mountpoint_clean),
                    native_unit_of_measurement=PERCENTAGE,
                    icon="mdi:harddisk",
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                True,
            )
            entities.append(entity)

        # carp interfaces
        for interface in state.get("carp_interfaces", []):
            uniqid = interface["uniqid"]
            entity = PfSenseCarpInterfaceSensor(
                config_entry,
                coordinator,
                SensorEntityDescription(
                    key=f"carp.interface.{uniqid}",
                    name="CARP Interface Status {} ({})".format(
                        uniqid, interface["descr"]
                    ),
                    icon="mdi:check-network-outline",
                ),
                True,
            )
            entities.append(entity)

        # interfaces
        for interface_name in dict_get(state, "telemetry.interfaces", {}).keys():
            interface = state["telemetry"]["interfaces"][interface_name]
            for property in [
                "status", "inerrs", "outerrs", "collisions", "inbytespass", 
                "inbytespass_kilobytes_per_second", "outbytespass", 
                "outbytespass_kilobytes_per_second", "inpktspass", 
                "inpktspass_packets_per_second", "outpktspass", 
                "outpktspass_packets_per_second", "inbytesblock", 
                "inbytesblock_kilobytes_per_second", "outbytesblock", 
                "outbytesblock_kilobytes_per_second", "inpktsblock", 
                "inpktsblock_packets_per_second", "outpktsblock", 
                "outpktsblock_packets_per_second", "inbytes", 
                "inbytes_kilobytes_per_second", "outbytes", 
                "outbytes_kilobytes_per_second", "inpkts", 
                "inpkts_packets_per_second", "outpkts", "outpkts_packets_per_second",
            ]:
                state_class = None
                native_unit_of_measurement = None
                icon = None
                enabled_default = False

                if property in ["status", "inbytes_kilobytes_per_second", "outbytes_kilobytes_per_second", "inpkts_packets_per_second", "outpkts_packets_per_second"]:
                    enabled_default = True

                if "_packets_per_second" in property or "_kilobytes_per_second" in property:
                    state_class = SensorStateClass.MEASUREMENT

                if "_packets_per_second" in property:
                    native_unit_of_measurement = DATA_RATE_PACKETS_PER_SECOND

                if "_kilobytes_per_second" in property:
                    native_unit_of_measurement = UnitOfDataRate.KILOBYTES_PER_SECOND

                if native_unit_of_measurement is None:
                    if "bytes" in property:
                        native_unit_of_measurement = UnitOfInformation.BYTES
                        state_class = SensorStateClass.TOTAL_INCREASING
                    if "pkts" in property:
                        native_unit_of_measurement = DATA_PACKETS
                        state_class = SensorStateClass.TOTAL_INCREASING

                if property in ["inerrs", "outerrs", "collisions"]:
                    native_unit_of_measurement = COUNT

                if "pkts" in property or "bytes" in property:
                    icon = "mdi:server-network"
                if property == "status":
                    icon = "mdi:check-network-outline"
                if icon is None:
                    icon = "mdi:gauge"

                entity = PfSenseInterfaceSensor(
                    config_entry,
                    coordinator,
                    SensorEntityDescription(
                        key="telemetry.interface.{}.{}".format(interface["ifname"], property),
                        name="Interface {} {}".format(interface["descr"], property),
                        native_unit_of_measurement=native_unit_of_measurement,
                        icon=icon,
                        state_class=state_class,
                    ),
                    enabled_default,
                )
                entities.append(entity)

        # gateways
        for gateway_name in dict_get(state, "telemetry.gateways", {}).keys():
            gateway = state["telemetry"]["gateways"][gateway_name]
            for property in ["status", "delay", "stddev", "loss"]:
                state_class = None
                native_unit_of_measurement = None
                icon = "mdi:router-network"
                enabled_default = True

                if property == "loss":
                    native_unit_of_measurement = PERCENTAGE
                if property in ["delay", "stddev"]:
                    native_unit_of_measurement = UnitOfTime.MILLISECONDS
                if property == "status":
                    icon = "mdi:check-network-outline"

                entity = PfSenseGatewaySensor(
                    config_entry,
                    coordinator,
                    SensorEntityDescription(
                        key="telemetry.gateway.{}.{}".format(gateway["name"], property),
                        name="Gateway {} {}".format(gateway["name"], property),
                        native_unit_of_measurement=native_unit_of_measurement,
                        icon=icon,
                        state_class=state_class,
                    ),
                    enabled_default,
                )
                entities.append(entity)

        # openvpn servers
        for vpnid in dict_get(state, "telemetry.openvpn.servers", {}).keys():
            servers = dict_get(state, "telemetry.openvpn.servers", {})
            server = servers[vpnid]
            for property in [
                "connected_client_count", "total_bytes_recv", "total_bytes_sent",
                "total_bytes_recv_kilobytes_per_second", "total_bytes_sent_kilobytes_per_second",
            ]:
                state_class = None
                native_unit_of_measurement = None
                icon = None
                enabled_default = False

                if "_kilobytes_per_second" in property:
                    state_class = SensorStateClass.MEASUREMENT
                    native_unit_of_measurement = UnitOfDataRate.KILOBYTES_PER_SECOND

                if property == "connected_client_count":
                    state_class = SensorStateClass.MEASUREMENT
                    native_unit_of_measurement = "clients"
                    icon = "mdi:ip-network-outline"

                if native_unit_of_measurement is None and "bytes" in property:
                    native_unit_of_measurement = UnitOfInformation.BYTES
                    icon = "mdi:server-network"

                if icon is None:
                    icon = "mdi:gauge"

                entity = PfSenseOpenVPNServerSensor(
                    config_entry,
                    coordinator,
                    SensorEntityDescription(
                        key="telemetry.openvpn.servers.{}.{}".format(vpnid, property),
                        name="OpenVPN Server {} ({}) {}".format(vpnid, server["name"], property),
                        native_unit_of_measurement=native_unit_of_measurement,
                        icon=icon,
                        state_class=state_class,
                    ),
                    enabled_default,
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


def normalize_filesystem_device_name(device_name):
    return device_name.replace("/", "_slash_").strip("_")


class PfSenseSensor(PfSenseEntity, SensorEntity):
    def __init__(
        self,
        config_entry,
        coordinator: DataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        enabled_default: bool,
    ) -> None:
        self.config_entry = config_entry
        self.entity_description = entity_description
        self.coordinator = coordinator
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_name = f"{self.pfsense_device_name} {entity_description.name}"
        self._attr_unique_id = slugify(
            f"{self.pfsense_device_unique_id}_{entity_description.key}"
        )
        self._previous_value = None


class PfSenseStaticKeySensor(PfSenseSensor):
    @property
    def available(self) -> bool:
        value = self._get_pfsense_state_value(self.entity_description.key)
        if value is None:
            return False

        if value == 0 and self.entity_description.key == "telemetry.system.temp":
            return False

        if value == 0 and self.entity_description.key == "telemetry.cpu.frequency.current":
            if self._previous_value is None:
                return False

        return super().available

    @property
    def native_value(self):
        value = self._get_pfsense_state_value(self.entity_description.key)
        if value is None:
            if self.entity_description.key == "telemetry.system.boottime":
                return value
            return STATE_UNKNOWN

        if value == 0 and self.entity_description.key == "telemetry.system.temp":
            return STATE_UNKNOWN

        if self.entity_description.key == "telemetry.system.boottime":
            return utc_from_timestamp(value)

        if self.entity_description.key == "telemetry.cpu.frequency.current":
            if value == 0 and self._previous_value is not None:
                value = self._previous_value
            if value == 0:
                return STATE_UNKNOWN

        self._previous_value = value
        return value


class PfSenseFilesystemSensor(PfSenseSensor):
    def _pfsense_get_filesystem(self):
        state = self.coordinator.data
        if not state: return None
        for filesystem in dict_get(state, "telemetry.filesystems", []):
            device_clean = normalize_filesystem_device_name(filesystem["device"])
            if self.entity_description.key == f"telemetry.filesystems.{device_clean}":
                return filesystem
        return None

    @property
    def available(self) -> bool:
        return self._pfsense_get_filesystem() is not None and super().available

    @property
    def native_value(self):
        filesystem = self._pfsense_get_filesystem()
        return filesystem["percent_used"]

    @property
    def extra_state_attributes(self):
        attributes = {}
        filesystem = self._pfsense_get_filesystem()
        for attr in ["device", "type", "total_size", "mountpoint"]:
            attributes[attr] = filesystem[attr]
        return attributes


class PfSenseInterfaceSensor(PfSenseSensor):
    def _pfsense_get_interface_property_name(self):
        return self.entity_description.key.split(".")[3]

    def _pfsense_get_interface_name(self):
        return self.entity_description.key.split(".")[2]

    def _pfsense_get_interface(self):
        state = self.coordinator.data
        if not state: return None
        interface_name = self._pfsense_get_interface_name()
        return dict_get(state, f"telemetry.interfaces.{interface_name}")

    @property
    def available(self) -> bool:
        interface = self._pfsense_get_interface()
        property = self._pfsense_get_interface_property_name()
        if interface is None or property not in interface.keys():
            return False
        return super().available

    @property
    def extra_state_attributes(self):
        attributes = {}
        interface = self._pfsense_get_interface()
        for attr in ["hwif", "enable", "if", "macaddr", "mtu", "media"]:
            if attr in interface:
                attributes[attr] = interface[attr]
        return attributes

    @property
    def icon(self):
        property = self._pfsense_get_interface_property_name()
        if property == "status" and self.native_value != "up":
            return "mdi:close-network-outline"
        return super().icon

    @property
    def native_value(self):
        interface = self._pfsense_get_interface()
        property = self._pfsense_get_interface_property_name()
        return interface.get(property, STATE_UNKNOWN)


class PfSenseCarpInterfaceSensor(PfSenseSensor):
    def _pfsense_get_interface_name(self):
        return self.entity_description.key.split(".")[2]

    def _pfsense_get_interface(self):
        state = self.coordinator.data
        if not state: return None
        interface_name = self._pfsense_get_interface_name()
        for i_interface in state.get("carp_interfaces", []):
            if i_interface["uniqid"] == interface_name:
                return i_interface
        return None

    @property
    def extra_state_attributes(self):
        attributes = {}
        interface = self._pfsense_get_interface()
        for attr in ["interface", "vhid", "advskew", "advbase", "type", "subnet_bits", "subnet"]:
            attributes[attr] = interface[attr]
        return attributes

    @property
    def available(self) -> bool:
        return self._pfsense_get_interface() is not None and super().available

    @property
    def icon(self):
        if self.native_value != "MASTER":
            return "mdi:close-network-outline"
        return super().icon

    @property
    def native_value(self):
        interface = self._pfsense_get_interface()
        return interface.get("status", STATE_UNKNOWN)


class PfSenseGatewaySensor(PfSenseSensor):
    def _pfsense_get_gateway_property_name(self):
        return self.entity_description.key.split(".")[3]

    def _pfsense_get_gateway_name(self):
        return self.entity_description.key.split(".")[2]

    def _pfsense_get_gateway(self):
        state = self.coordinator.data
        if not state: return None
        gateway_name = self._pfsense_get_gateway_name()
        return dict_get(state, f"telemetry.gateways.{gateway_name}")

    def _pfsense_get_gateway_details(self):
        state = self.coordinator.data
        if not state: return None
        gateway_name = self._pfsense_get_gateway_name()
        return dict_get(state, f"telemetry.gateways_detail.{gateway_name}")

    @property
    def available(self) -> bool:
        gateway = self._pfsense_get_gateway()
        property = self._pfsense_get_gateway_property_name()
        if gateway is None or property not in gateway.keys():
            return False

        if property in ["stddev", "delay", "loss"]:
            value = gateway[property]
            if isinstance(value, str):
                value = re.sub(r"[^0-9.]*", "", value)
                if len(value) < 1:
                    return False

        return super().available

    @property
    def extra_state_attributes(self):
        attributes = {}
        gateway = self._pfsense_get_gateway()
        gateway_detail = self._pfsense_get_gateway_details()
        for attr in ["monitorip", "srcip", "substatus"]:
            value = gateway[attr]
            if attr == "substatus" and gateway[attr] == "none":
                value = None
            attributes[attr] = value

        if gateway_detail:
            for attr in ["weight", "isdefaultgw", "interface", "gateway"]:
                if attr in gateway_detail:
                    attributes[attr] = gateway_detail[attr]
                elif attr == "isdefaultgw":
                    attributes[attr] = False
        return attributes

    @property
    def icon(self):
        property = self._pfsense_get_gateway_property_name()
        if property == "status" and self.native_value != "online":
            return "mdi:close-network-outline"
        return super().icon

    @property
    def native_value(self):
        gateway = self._pfsense_get_gateway()
        property = self._pfsense_get_gateway_property_name()

        if gateway is None:
            return STATE_UNKNOWN

        try:
            value = gateway[property]
            if property in ["stddev", "delay", "loss"] and isinstance(value, str):
                value = re.sub(r"[^0-9.]*", "", value)
                if len(value) > 0:
                    value = float(value)

            if isinstance(value, str) and len(value) < 1:
                return STATE_UNKNOWN

            return value
        except KeyError:
            return STATE_UNKNOWN


class PfSenseOpenVPNServerSensor(PfSenseSensor):
    def _pfsense_get_server_property_name(self):
        return self.entity_description.key.split(".")[4]

    def _pfsense_get_server_vpnid(self):
        return self.entity_description.key.split(".")[3]

    def _pfsense_get_server(self):
        state = self.coordinator.data
        if not state: return None
        vpnid = self._pfsense_get_server_vpnid()
        return dict_get(state, f"telemetry.openvpn.servers.{vpnid}")

    @property
    def available(self) -> bool:
        server = self._pfsense_get_server()
        property = self._pfsense_get_server_property_name()
        if server is None or property not in server.keys():
            return False
        return super().available

    @property
    def extra_state_attributes(self):
        attributes = {}
        server = self._pfsense_get_server()
        if server is None:
            return attributes
        for attr in ["vpnid", "name"]:
            attributes[attr] = server[attr]
        return attributes

    @property
    def native_value(self):
        server = self._pfsense_get_server()
        property = self._pfsense_get_server_property_name()
        if server is None:
            return STATE_UNKNOWN
        return server.get(property, STATE_UNKNOWN)