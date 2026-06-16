import xmlrpc.client
from unittest.mock import patch, MagicMock

from custom_components.pfsense.pypfsense import (
    Client,
    dict_get,
    normalize_service_data,
)


def test_dict_get():
    """Test the robust dictionary deep-get helper."""
    data = {
        "telemetry": {
            "system": {"version": "2.6.0"},
            # FIX: Ensure these are actual integer keys, not strings!
            "interfaces": {0: {"status": "up"}},
            2: "numeric_key_test",
        }
    }

    assert dict_get(data, "telemetry.system.version") == "2.6.0"
    assert dict_get(data, "telemetry.interfaces.0.status") == "up"
    assert dict_get(data, "telemetry.2") == "numeric_key_test"


def test_normalize_service_data():
    assert normalize_service_data({"name": "dhcpd"}) == {"name": "dhcpd"}
    assert normalize_service_data(None) == {}
    assert normalize_service_data('{"name": "dpinger"}') == {"name": "dpinger"}


@patch("custom_components.pfsense.pypfsense.xmlrpc.client.ServerProxy")
def test_client_initialization(mock_server_proxy):
    client_insecure = Client(
        "https://192.168.1.1", "admin", "password", {"verify_ssl": False}
    )
    # FIX: Verify the stripped URL path
    assert "192.168.1.1/xmlrpc.php" in client_insecure._url


@patch("custom_components.pfsense.pypfsense.xmlrpc.client.ServerProxy")
def test_client_php_execution_and_parsing(mock_server_proxy):
    mock_proxy_instance = MagicMock()
    mock_server_proxy.return_value = mock_proxy_instance

    client = Client("https://192.168.1.1", "admin", "password")

    # 1. Test Firmware Version (XMLRPC direct method)
    mock_proxy_instance.pfsense.host_firmware_version.return_value = "2.6.0-RELEASE"
    version = client.get_host_firmware_version()
    assert "2.6.0" in str(version)

    # 2. Test ARP Table Retrieval (exec_php)
    client._exec_php = MagicMock()
    client._exec_php.return_value = {
        "data": [{"mac-address": "aa:bb:cc:dd:ee:ff", "ip-address": "10.0.0.1"}]
    }
    arp_table = client.get_arp_table()
    assert len(arp_table) == 1


@patch("custom_components.pfsense.pypfsense.xmlrpc.client.ServerProxy")
def test_client_exception_handling(mock_server_proxy):
    mock_proxy_instance = MagicMock()
    mock_server_proxy.return_value = mock_proxy_instance
    client = Client("https://192.168.1.1", "admin", "password")

    mock_proxy_instance.pfsense.exec_php.side_effect = xmlrpc.client.Fault(
        1, "Authentication Failed"
    )
    try:
        client.get_telemetry()
    except xmlrpc.client.Fault:
        pass
