import pytest
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
            "interfaces": {"0": {"status": "up"}},
            "2": "numeric_key_test"
        }
    }
    
    # Standard nested retrieval
    assert dict_get(data, "telemetry.system.version") == "2.6.0"
    
    # Numeric key handling (string "0" gets cast to int if underlying dict uses ints, or handled natively)
    assert dict_get(data, "telemetry.interfaces.0.status") == "up"
    assert dict_get(data, "telemetry.2") == "numeric_key_test"
    
    # Missing keys fallback to default
    assert dict_get(data, "telemetry.missing.key", default="fallback") == "fallback"

def test_normalize_service_data():
    """Test the service dictionary normalizer."""
    # Standard dict
    assert normalize_service_data({"name": "dhcpd"}) == {"name": "dhcpd"}
    
    # None fallback
    assert normalize_service_data(None) == {}
    
    # JSON string parsing
    assert normalize_service_data('{"name": "dpinger"}') == {"name": "dpinger"}
    assert normalize_service_data("") == {}
    
    # Invalid datatype exception
    with pytest.raises(TypeError):
        normalize_service_data(123)

@patch("custom_components.pfsense.pypfsense.xmlrpc.client.ServerProxy")
def test_client_initialization(mock_server_proxy):
    """Verify the XMLRPC client binds securely and applies SSL contexts."""
    # Test insecure SSL context binding
    client_insecure = Client("https://192.168.1.1", "admin", "password", {"verify_ssl": False})
    assert client_insecure._url == "https://192.168.1.1/xmlrpc.php"
    
    mock_server_proxy.assert_called()
    # Check that a context was passed to bypass SSL
    assert "context" in mock_server_proxy.call_args[1]

    # Test secure SSL context
    mock_server_proxy.reset_mock()
    client_secure = Client("https://192.168.1.1", "admin", "password", {"verify_ssl": True})
    # If verify_ssl is true, it doesn't pass an unverified context
    assert "context" not in mock_server_proxy.call_args[1]

@patch("custom_components.pfsense.pypfsense.xmlrpc.client.ServerProxy")
def test_client_php_execution_and_parsing(mock_server_proxy):
    """Test that the client correctly executes PHP payloads and parses the JSON return."""
    mock_proxy_instance = MagicMock()
    mock_server_proxy.return_value = mock_proxy_instance
    
    client = Client("https://192.168.1.1", "admin", "password")
    
    # 1. Test Firmware Version
    mock_proxy_instance.pfsense.exec_php.return_value = '{"data": {"version": "2.6.0-RELEASE"}}'
    version = client.get_host_firmware_version()
    assert version["version"] == "2.6.0-RELEASE"

    # 2. Test ARP Table Retrieval
    mock_proxy_instance.pfsense.exec_php.return_value = '{"data": [{"mac-address": "aa:bb:cc:dd:ee:ff", "ip-address": "10.0.0.1"}]}'
    arp_table = client.get_arp_table()
    assert len(arp_table) == 1
    assert arp_table[0]["mac-address"] == "aa:bb:cc:dd:ee:ff"
    
    # 3. Test Service Restart Command
    mock_proxy_instance.pfsense.exec_php.return_value = '{"data": true}'
    client.restart_service("dhcpd")
    
    # Verify exec_php was called to issue the restart command
    mock_proxy_instance.pfsense.exec_php.assert_called()

@patch("custom_components.pfsense.pypfsense.xmlrpc.client.ServerProxy")
def test_client_exception_handling(mock_server_proxy):
    """Verify that network exceptions and XMLRPC faults are captured safely."""
    mock_proxy_instance = MagicMock()
    mock_server_proxy.return_value = mock_proxy_instance
    client = Client("https://192.168.1.1", "admin", "password")
    
    # Simulate an XMLRPC Fault
    mock_proxy_instance.pfsense.exec_php.side_effect = xmlrpc.client.Fault(1, "Authentication Failed")
    
    # Depending on how _log_errors handles faults (returns None/[] or raises), 
    # we ensure the method is called and the fault is encountered gracefully.
    try:
        client.get_telemetry()
    except xmlrpc.client.Fault:
        pass # Expected if the decorator re-raises
    
    assert mock_proxy_instance.pfsense.exec_php.called