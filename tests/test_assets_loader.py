import unittest
from unittest.mock import patch
import os
import shutil
from utils.assets import BikeAssetLoader

class TestBikeAssetLoader(unittest.TestCase):
    def setUp(self):
        self.loader = BikeAssetLoader()
        self.test_assets_dir = "test_assets_bikes"
        if not os.path.exists(self.test_assets_dir):
            os.makedirs(self.test_assets_dir)
        self.loader.assets_path = self.test_assets_dir

    def tearDown(self):
        if os.path.exists(self.test_assets_dir):
            shutil.rmtree(self.test_assets_dir)

    def test_source_1_verified_urls(self):
        # Classic 350 should have a verified URL
        url = self.loader.get_asset_url("Classic 350")
        self.assertTrue(url.startswith("http"))
        self.assertIn("unsplash", url.lower())

    def test_source_2_local_assets_valid(self):
        # Create a valid image file (> 50KB)
        # Use a model NOT in VERIFIED_URLS
        img_path = os.path.join(self.test_assets_dir, "Goan_Classic_350.jpg")
        with open(img_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"0" * 60000) # Fake JPEG header + 60KB data
        
        url = self.loader.get_asset_url("Goan Classic 350")
        self.assertTrue(url.startswith("data:image/jpg;base64,"))

    @patch('utils.assets.BikeAssetLoader._search_fallback')
    def test_source_2_local_assets_invalid_html(self, mock_search):
        mock_search.return_value = None
        # Create an invalid HTML file disguised as JPG
        # Use a model NOT in VERIFIED_URLS
        img_path = os.path.join(self.test_assets_dir, "Super_Meteor_650.jpg")
        with open(img_path, "wb") as f:
            f.write(b"<!DOCTYPE HTML><html></html>")
        
        url = self.loader.get_asset_url("Super Meteor 650")
        # Should NOT be the local one
        self.assertFalse(url.startswith("data:image/jpg;base64,"))
        mock_search.assert_called_once()

    @patch('utils.assets.BikeAssetLoader._search_fallback')
    def test_source_2_local_assets_too_small(self, mock_search):
        mock_search.return_value = None
        # Create a small valid image file (< 50KB)
        img_path = os.path.join(self.test_assets_dir, "Scram_440.jpg")
        with open(img_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"0" * 1000)
        
        url = self.loader.get_asset_url("Scram 440")
        self.assertFalse(url.startswith("data:image/jpg;base64,"))
        mock_search.assert_called_once()

    @patch('utils.assets.BikeAssetLoader._search_fallback')
    def test_source_3_search_fallback(self, mock_search):
        mock_search.return_value = "http://search-result.com/bike.jpg"
        
        # Use a model NOT in VERIFIED_URLS and no local asset
        url = self.loader.get_asset_url("Non Existent Bike")
        self.assertEqual(url, "http://search-result.com/bike.jpg")
        mock_search.assert_called_once()

    @patch('utils.assets.BikeAssetLoader._search_fallback')
    def test_fallback_image(self, mock_search):
        mock_search.return_value = None
        # Unknown model should return fallback
        url = self.loader.get_asset_url("Unknown Bike")
        self.assertEqual(url, self.loader.FALLBACK_URL)

if __name__ == "__main__":
    unittest.main()
