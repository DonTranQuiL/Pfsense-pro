import pytest
from unittest.mock import patch, MagicMock
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.const import CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_VERIFY_SSL

from custom_components.pfsense.const import DOMAIN, CONF_DEVICES

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield

@pytest.mark.asyncio
async def test_form_user_success(hass):
    """Test successful initial config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM

    with patch("custom_components.pfsense.config_flow.Client") as mock_client_cls, \
         patch("custom_components.pfsense.async_setup_entry", return_value=True):
        
        mock_client = MagicMock()
        # Mock successful connection
        mock_client.get_host_firmware_version.return_value = {"version": "2.6.0"}
        mock_client_cls.return_value = mock_client

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://192.168.1.1",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password123",
                CONF_VERIFY_SSL: False,
            },
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "192.168.1.1"
    assert result2["data"][CONF_URL] == "https://192.168.1.1"


@pytest.mark.asyncio
async def test_options_flow(hass):
    """Test options flow successfully reads the ARP table to populate tracking devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "https://192.168.1.1", CONF_USERNAME: "admin", CONF_PASSWORD: "pwd"},
        options={CONF_DEVICES: ["aa:bb:cc:dd:ee:ff"]},
    )
    entry.add_to_hass(hass)

    with patch("custom_components.pfsense.config_flow.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_arp_table.return_value = [
            {"mac-address": "11:22:33:44:55:66", "hostname": "Test-PC", "ip-address": "192.168.1.10"}
        ]
        mock_client_cls.return_value = mock_client

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "device_tracker"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICES: ["11:22:33:44:55:66"]},
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"][CONF_DEVICES] == ["11:22:33:44:55:66"]