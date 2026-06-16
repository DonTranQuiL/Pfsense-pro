import pytest
from unittest.mock import MagicMock
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pfsense.const import DOMAIN
from custom_components.pfsense.binary_sensor import (
    PfSenseCarpStatusBinarySensor,
    PfSensePendingNoticesPresentBinarySensor,
)
from homeassistant.components.binary_sensor import BinarySensorEntityDescription


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = {
        "carp_status": True,
        "notices": {
            "pending_notices_present": True,
            "pending_notices": [{"msg": "Update available"}],
        },
    }
    return coord


def test_binary_sensors(mock_coordinator):
    """Test the boolean threshold logic for CARP and Notices."""
    config_entry = MockConfigEntry(domain=DOMAIN)

    carp_desc = BinarySensorEntityDescription(key="carp.status", name="CARP")
    carp_sensor = PfSenseCarpStatusBinarySensor(
        config_entry, mock_coordinator, carp_desc, False
    )
    carp_sensor.pfsense_device_name = "pfSense"
    carp_sensor.pfsense_device_unique_id = "test"

    assert carp_sensor.is_on is True

    notice_desc = BinarySensorEntityDescription(key="notices", name="Notices")
    notice_sensor = PfSensePendingNoticesPresentBinarySensor(
        config_entry, mock_coordinator, notice_desc, False
    )
    notice_sensor.pfsense_device_name = "pfSense"
    notice_sensor.pfsense_device_unique_id = "test"

    assert notice_sensor.is_on is True
    assert (
        notice_sensor.extra_state_attributes["pending_notices"][0]["msg"]
        == "Update available"
    )
