import pytest
from unittest.mock import MagicMock, patch
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pfsense.const import DOMAIN, PLATFORMS
from custom_components.pfsense import async_setup_entry, async_unload_entry
from homeassistant.const import CONF_URL, CONF_USERNAME, CONF_PASSWORD

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield

@pytest.mark.asyncio
async def test_setup_and_unload_entry(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN, 
        data={CONF_URL: "https://192.168.1.1", CONF_USERNAME: "admin", CONF_PASSWORD: "pwd"},
        options={"device_tracker_enabled": True},
        entry_id="test_pfsense"
    )
    entry.add_to_hass(hass)

    with patch("custom_components.pfsense.pfSenseClient") as mock_client_cls, \
         patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups", return_value=True) as mock_forward, \
         patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_config_entry_first_refresh", return_value=None):
         
        mock_client = MagicMock()
        mock_client.get_host_firmware_version.return_value = {"version": "2.6.0"}
        mock_client.get_telemetry.return_value = {"system": {}}
        mock_client_cls.return_value = mock_client

        assert await async_setup_entry(hass, entry) is True
        assert mock_forward.called
        assert DOMAIN in hass.data

    with patch("homeassistant.config_entries.ConfigEntries.async_unload_platforms", return_value=True) as mock_unload:
        assert await async_unload_entry(hass, entry) is True
        assert mock_unload.called
        assert entry.entry_id not in hass.data.get(DOMAIN, {})