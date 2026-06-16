import pytest
from unittest.mock import patch, MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pfsense.const import DOMAIN, COORDINATOR
from custom_components.pfsense.binary_sensor import PfSenseCarpStatusBinarySensor


@pytest.fixture
def mock_pfsense_client():
    """Mock the pfSense client for binary sensor tests."""
    mock_client = MagicMock()
    mock_client.get_system_info.return_value = {
        "hostname": "router",
        "domain": "local",
        "netgate_device_id": "mock_id_12345",
    }
    mock_client.get_host_firmware_version.return_value = {
        "platform": "pfSense",
        "firmware": {"version": "2.6.0"},
    }
    # Provide empty iterables to prevent coordinator dict_get crashes
    mock_client.get_telemetry.return_value = {}
    mock_client.get_config.return_value = {}
    mock_client.get_interfaces.return_value = {}
    mock_client.get_services.return_value = []
    mock_client.get_carp_interfaces.return_value = []
    mock_client.get_dhcp_leases.return_value = []
    return mock_client


@pytest.mark.asyncio
async def test_binary_sensors_active(hass: HomeAssistant, mock_pfsense_client):
    """Test binary sensors when states are True/Active."""

    # Simulate an active CARP node with pending system notices
    mock_pfsense_client.get_carp_status.return_value = True
    mock_pfsense_client.are_notices_pending.return_value = True
    mock_pfsense_client.get_notices.return_value = {"id_1": "Update available"}

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="router.local",
        data={
            "url": "https://192.168.1.1",
            "username": "admin",
            "password": "password",
        },
        options={"device_tracker_enabled": False},
        entry_id="pfsense_binary_test_on",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.pfsense.pfSenseClient", return_value=mock_pfsense_client
        ),
        patch("custom_components.pfsense.async_load_cache", return_value=None),
        patch("custom_components.pfsense.async_save_cache"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # 1. Pending Notices Sensor (Enabled by default, so it exists in the state machine)
    notices_sensor = hass.states.get(
        "binary_sensor.router_local_pending_notices_present"
    )
    assert notices_sensor is not None
    assert notices_sensor.state == STATE_ON

    # Check attributes and device class
    assert (
        notices_sensor.attributes.get("device_class") == BinarySensorDeviceClass.PROBLEM
    )
    assert notices_sensor.attributes.get("pending_notices") == {
        "id_1": "Update available"
    }

    # 2. CARP Status Sensor (Disabled by default, so we test the class logic directly against the coordinator)
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    carp_entity = PfSenseCarpStatusBinarySensor(
        entry,
        coordinator,
        BinarySensorEntityDescription(key="carp.status", name="CARP Status"),
        False,
    )
    assert carp_entity.is_on is True


@pytest.mark.asyncio
async def test_binary_sensors_inactive(hass: HomeAssistant, mock_pfsense_client):
    """Test binary sensors when states are False/Inactive."""

    # Simulate an inactive CARP node with no system notices
    mock_pfsense_client.get_carp_status.return_value = False
    mock_pfsense_client.are_notices_pending.return_value = False
    mock_pfsense_client.get_notices.return_value = {}

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="router.local",
        data={
            "url": "https://192.168.1.1",
            "username": "admin",
            "password": "password",
        },
        options={"device_tracker_enabled": False},
        entry_id="pfsense_binary_test_off",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.pfsense.pfSenseClient", return_value=mock_pfsense_client
        ),
        patch("custom_components.pfsense.async_load_cache", return_value=None),
        patch("custom_components.pfsense.async_save_cache"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # 1. Pending Notices Sensor
    notices_sensor = hass.states.get(
        "binary_sensor.router_local_pending_notices_present"
    )
    assert notices_sensor is not None
    assert notices_sensor.state == STATE_OFF
    assert notices_sensor.attributes.get("pending_notices") == {}

    # 2. CARP Status Sensor
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    carp_entity = PfSenseCarpStatusBinarySensor(
        entry,
        coordinator,
        BinarySensorEntityDescription(key="carp.status", name="CARP Status"),
        False,
    )
    assert carp_entity.is_on is False
