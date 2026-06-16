import pytest
from unittest.mock import MagicMock, patch, AsyncMock, PropertyMock
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.components.switch import SwitchEntityDescription

from custom_components.pfsense.switch import PfSenseServiceSwitch


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = {
        "services": [{"name": "dhcpd", "status": True, "description": "DHCP Server"}]
    }
    coord.async_refresh = AsyncMock()
    return coord


@pytest.mark.asyncio
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
async def test_service_switch(mock_name, mock_uid, mock_coordinator):
    config_entry = MockConfigEntry()
    desc = SwitchEntityDescription(key="services.dhcpd.status", name="DHCPD")

    # Safely handle the constructor signature
    try:
        switch = PfSenseServiceSwitch(config_entry, mock_coordinator, desc, False)
    except TypeError:
        switch = PfSenseServiceSwitch(config_entry, mock_coordinator, desc)

    mock_client = MagicMock()
    switch._get_pfsense_client = MagicMock(return_value=mock_client)
    switch.hass = MagicMock()
    switch.hass.async_add_executor_job = AsyncMock()

    assert switch.is_on is True

    await switch.async_turn_off()
    switch.hass.async_add_executor_job.assert_called_with(
        mock_client.stop_service,
        "dhcpd",
        {"name": "dhcpd", "status": True, "description": "DHCP Server"},
    )
