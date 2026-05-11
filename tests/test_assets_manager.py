import os
import pytest
import requests
from unittest.mock import patch, MagicMock
from utils.assets_manager import download_bike_image

@pytest.fixture
def temp_assets_dir(tmp_path):
    """Fixture to provide a temporary directory for assets."""
    d = tmp_path / "assets"
    d.mkdir()
    return str(d)

def test_download_bike_image_success(temp_assets_dir):
    """Test successful image download using mocks."""
    bike_name = "Classic 350"
    mock_content = b"fake image content"
    
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_content
        mock_get.return_value = mock_response
        
        file_path = download_bike_image(bike_name, temp_assets_dir)
        
        assert os.path.exists(file_path)
        assert bike_name.replace(" ", "_") in file_path
        with open(file_path, "rb") as f:
            assert f.read() == mock_content

def test_download_bike_image_official_fallback(temp_assets_dir):
    """Test that it uses official URL fallback."""
    bike_name = "Classic 350"
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"content"
        mock_get.return_value = mock_response
        
        download_bike_image(bike_name, temp_assets_dir)
        
        # Verify it was called with the official URL
        from utils.assets_manager import OFFICIAL_URLS
        mock_get.assert_called_with(OFFICIAL_URLS[bike_name], timeout=pytest.approx(10, abs=10))

def test_download_bike_image_scrape_fallback(temp_assets_dir):
    """Test that it falls back to scraping if official URL is missing."""
    bike_name = "Non Existent Bike"
    mock_url = "http://example.com/scraped.jpg"
    
    with patch("utils.assets_manager.scrape_image_url") as mock_scrape:
        mock_scrape.return_value = mock_url
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"scraped content"
            mock_get.return_value = mock_response
            
            download_bike_image(bike_name, temp_assets_dir)
            
            mock_scrape.assert_called_with(bike_name)
            mock_get.assert_called_with(mock_url, timeout=pytest.approx(10, abs=10))

def test_download_bike_image_network_error(temp_assets_dir):
    """Test handling of network errors."""
    bike_name = "Classic 350"
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with pytest.raises(requests.exceptions.ConnectionError):
            download_bike_image(bike_name, temp_assets_dir)

def test_scrape_all_bikes(temp_assets_dir, tmp_path):
    """Test the batch processing function."""
    from utils.assets_manager import scrape_all_bikes
    
    # Create a dummy structure file
    structure = {
        "models": [
            {"text": "Classic 350"},
            {"text": "Bullet 350"},
            {"text": "All"} # Should be skipped
        ]
    }
    structure_path = tmp_path / "structure.json"
    import json
    with open(structure_path, "w") as f:
        json.dump(structure, f)
        
    with patch("utils.assets_manager.download_bike_image") as mock_download:
        mock_download.return_value = "/fake/path"
        
        results = scrape_all_bikes(str(structure_path), temp_assets_dir)
        
        assert "Classic 350" in results
        assert "Bullet 350" in results
        assert "All" not in results
        assert mock_download.call_count == 2
