import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pfsense.const import DOMAIN
from custom_components.pfsense.sensor import PfSenseOpenVPNServerSensor
from homeassistant.components.sensor import SensorEntityDescription


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = {
        "telemetry": {
            "openvpn": {
                "servers": {"1": {"vpnid": "1", "name": "TestVPN", "status": "up"}}
            }
        }
    }
    return coord


@patch(
    "custom_components.pfsense.PfSenseEntity.pfsense_device_unique_id",
    new_callable=PropertyMock,
    return_value="test",
)
@patch(
    "custom_components.pfsense.PfSenseEntity.pfsense_device_name",
    new_callable=PropertyMock,
    return_value="pfSense",
)
def test_openvpn_sensor(mock_name, mock_uid, mock_coordinator):
    config_entry = MockConfigEntry(domain=DOMAIN)
    desc = SensorEntityDescription(
        key="telemetry.openvpn.servers.1.status", name="VPN Status"
    )

    # Init safely via property mocks
    sensor = PfSenseOpenVPNServerSensor(config_entry, mock_coordinator, desc, False)

    assert sensor._pfsense_get_server_vpnid() == "1"
    assert sensor._pfsense_get_server_property_name() == "status"
    assert sensor.native_value == "up"
    assert sensor.extra_state_attributes["name"] == "TestVPN"
