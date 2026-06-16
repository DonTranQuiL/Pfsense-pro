import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.components.switch import SwitchEntityDescription

from custom_components.pfsense.switch import PfSenseServiceSwitch

@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.data = {
        "services": [
            {"name": "dhcpd", "status": True, "description": "DHCP Server"}
        ]
    }
    coord.async_refresh = AsyncMock()
    return coord

@pytest.mark.asyncio
async def test_service_switch(mock_coordinator):
    """Test switch safely toggles pfSense internal services."""
    config_entry = MockConfigEntry()
    desc = SwitchEntityDescription(key="services.dhcpd.status", name="DHCPD")
    
    switch = PfSenseServiceSwitch(config_entry, mock_coordinator, desc, False)
    switch.pfsense_device_name = "pfSense"
    switch.pfsense_device_unique_id = "test"
    
    # Mock the client retrieval
    mock_client = MagicMock()
    switch._get_pfsense_client = MagicMock(return_value=mock_client)
    switch.hass = MagicMock()
    switch.hass.async_add_executor_job = AsyncMock()

    # Test reading state
    assert switch.is_on is True
    
    # Test turn off
    await switch.async_turn_off()
    switch.hass.async_add_executor_job.assert_called_with(
        mock_client.stop_service, "dhcpd", {"name": "dhcpd", "status": True, "description": "DHCP Server"}
    )
    mock_coordinator.async_refresh.assert_called_once()