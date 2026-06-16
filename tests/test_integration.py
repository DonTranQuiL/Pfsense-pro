import pytest
import xmlrpc.client
from unittest.mock import patch, MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pfsense.const import DOMAIN

# =========================================================================
# 1. MOCK DATA
# =========================================================================

MOCK_SYSTEM_INFO = {
    "hostname": "router",
    "domain": "local",
    "netgate_device_id": "mock_id_12345",
}

# =========================================================================
# 2. CONFIG FLOW TESTS
# =========================================================================


@pytest.mark.asyncio
async def test_config_flow_success(hass: HomeAssistant):
    """Test a successful config flow."""
    mock_client = MagicMock()
    mock_client.get_system_info.return_value = MOCK_SYSTEM_INFO

    # Patch the Client inside the config_flow file
    with (
        patch("custom_components.pfsense.config_flow.Client", return_value=mock_client),
        patch("custom_components.pfsense.async_setup_entry", return_value=True),
        patch("custom_components.pfsense.async_unload_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "https://192.168.1.1",
                "username": "admin",
                "password": "password",
                "verify_ssl": False,
            },
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "router.local"

        # Safe Cleanup
        for entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_config_flow_invalid_auth(hass: HomeAssistant):
    """Test config flow catches invalid xmlrpc authentication."""
    mock_client = MagicMock()
    # Simulate pfSense denying the login
    mock_client.get_system_info.side_effect = xmlrpc.client.Fault(
        1, "Invalid username or password"
    )

    with patch(
        "custom_components.pfsense.config_flow.Client", return_value=mock_client
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "https://192.168.1.1",
                "username": "admin",
                "password": "wrong_password",
                "verify_ssl": False,
            },
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "invalid_auth"}


# =========================================================================
# 3. COORDINATOR & SENSOR TESTS
# =========================================================================


@pytest.mark.asyncio
async def test_coordinator_sensor_extraction(hass: HomeAssistant):
    """Test full setup and sensor state extraction from pfSense telemetry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="router.local",
        data={
            "url": "https://192.168.1.1",
            "username": "admin",
            "password": "password",
            "verify_ssl": False,
        },
        # We disable device_tracker for the test to avoid MAC vendor lookups
        options={"device_tracker_enabled": False},
        entry_id="pfsense_test_id",
    )
    entry.add_to_hass(hass)

    # Build the massive mock response that pfSense would typically return
    mock_client = MagicMock()
    mock_client.get_system_info.return_value = MOCK_SYSTEM_INFO
    mock_client.get_host_firmware_version.return_value = {
        "platform": "pfSense",
        "firmware": {"version": "2.6.0"},
    }
    mock_client.get_telemetry.return_value = {
        "wan_ip": "100.100.100.100",
        "cpu": {"used_percent": 15, "frequency": {"current": 2000, "max": 3000}},
        "system": {
            "temp": 45.5,
            "boottime": 1600000000,
        },
    }

    # Fill in the required empty structures to prevent KeyErrors during dict_get
    mock_client.get_config.return_value = {}
    mock_client.get_interfaces.return_value = {}
    mock_client.get_services.return_value = []
    mock_client.get_carp_interfaces.return_value = []
    mock_client.get_carp_status.return_value = False
    mock_client.get_dhcp_leases.return_value = []
    mock_client.are_notices_pending.return_value = False
    mock_client.get_notices.return_value = {}

    # Patch the Client inside __init__.py and prevent the cache from writing
    with (
        patch("custom_components.pfsense.pfSenseClient", return_value=mock_client),
        patch("custom_components.pfsense.async_load_cache", return_value=None),
        patch("custom_components.pfsense.async_save_cache"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # 1. Verify WAN IP Sensor
    wan_ip_sensor = hass.states.get("sensor.router_local_wan_ip_address")
    assert wan_ip_sensor is not None
    assert wan_ip_sensor.state == "100.100.100.100"

    # 2. Verify CPU Usage Sensor
    cpu_sensor = hass.states.get("sensor.router_local_cpu_usage")
    assert cpu_sensor is not None
    assert cpu_sensor.state == "15"
