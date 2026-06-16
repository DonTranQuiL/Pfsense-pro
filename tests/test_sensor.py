import pytest
from unittest.mock import MagicMock
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


def test_openvpn_sensor(mock_coordinator):
    """Test the dynamic OpenVPN sensor property extraction."""
    config_entry = MockConfigEntry(domain=DOMAIN)

    # Simulate a key format: telemetry.openvpn.servers.1.status
    desc = SensorEntityDescription(
        key="telemetry.openvpn.servers.1.status", name="VPN Status"
    )

    sensor = PfSenseOpenVPNServerSensor(config_entry, mock_coordinator, desc, False)

    # We must patch the generic PfSenseEntity initialization properties that rely on config data
    sensor.pfsense_device_name = "pfSense"
    sensor.pfsense_device_unique_id = "pfsense_test"

    assert sensor._pfsense_get_server_vpnid() == "1"
    assert sensor._pfsense_get_server_property_name() == "status"
    assert sensor.native_value == "up"
    assert sensor.extra_state_attributes["name"] == "TestVPN"
