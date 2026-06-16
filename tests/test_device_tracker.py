from unittest.mock import MagicMock

from custom_components.pfsense.device_tracker import lookup_mac


def test_lookup_mac():
    """Verify MAC vendor lookup safely sanitizes and decodes."""
    mock_mac_lookup = MagicMock()
    # Mock behavior of sanitise and dictionary byte-prefixes
    mock_mac_lookup.sanitise.return_value = "AABBCCDDEEFF"
    mock_mac_lookup.prefixes = {b"AABBCC": b"Test Vendor Inc."}

    result = lookup_mac(mock_mac_lookup, "aa:bb:cc:dd:ee:ff")

    assert result == "Test Vendor Inc."
    mock_mac_lookup.sanitise.assert_called_with("aa:bb:cc:dd:ee:ff")
