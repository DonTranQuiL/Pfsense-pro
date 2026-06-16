import pytest
import xmlrpc.client
from unittest.mock import patch, MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pfsense.const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_DEVICE_TRACKER_ENABLED,
)
from homeassistant.const import (
    CONF_URL,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_VERIFY_SSL,
)

# =========================================================================
# CONFIG FLOW TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_form_user_success(hass: HomeAssistant):
    """Test successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    with patch("custom_components.pfsense.config_flow.Client") as mock_client_cls, \
         patch("custom_components.pfsense.async_setup_entry", return_value=True):
         
        mock_client = MagicMock()
        
        # THE FIX: Properly mock the system info so slugify doesn't crash!
        mock_client.get_system_info.return_value = {
            "hostname": "router",
            "domain": "local",
            "netgate_device_id": "mock_id_12345"
        }
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
        assert result2["title"] == "router.local"


@pytest.mark.asyncio
async def test_options_flow(hass: HomeAssistant):
    """Test the multi-step options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "https://192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "pwd",
        },
        options={CONF_DEVICES: []},
    )
    entry.add_to_hass(hass)

    with patch("custom_components.pfsense.config_flow.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_arp_table.return_value = [
            {
                "mac-address": "11:22:33:44:55:66",
                "hostname": "Test-PC",
                "ip-address": "192.168.1.10",
            }
        ]
        mock_client_cls.return_value = mock_client

        # Step 1: Init options flow
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

        # Step 2: THE FIX - Enable device tracker to trigger the next step!
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_TRACKER_ENABLED: True},
        )
        
        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "device_tracker"

        # Step 3: Now we can safely select the actual devices
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={CONF_DEVICES: ["11:22:33:44:55:66"]},
        )
        
        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_DEVICES] == ["11:22:33:44:55:66"]