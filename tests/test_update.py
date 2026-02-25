import pytest
from unittest.mock import patch, MagicMock
from app.update import get_latest_release_info, verify_signature, download_update
from pathlib import Path

@patch('app.update.requests.get')
def test_get_latest_release_info(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"tag_name": "v1.6.0", "assets": [], "html_url": "http://example.com"}
    mock_get.return_value = mock_response
    
    info = get_latest_release_info()
    assert info["version"] == "1.6.0"
    assert info["url"] == "http://example.com"

@patch('app.update.gnupg.GPG')
def test_verify_signature_no_key(mock_gpg):
    # Test behavior when PUBLIC_KEY_PATH doesn't exist
    with patch('app.update.PUBLIC_KEY_PATH', Path('/non/existent/path')):
        assert verify_signature(Path('test.file')) is True

@patch('app.update.requests.get')
def test_download_update_failed(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response
    
    assert download_update("http://example.com/file", Path("test.dest")) is False
