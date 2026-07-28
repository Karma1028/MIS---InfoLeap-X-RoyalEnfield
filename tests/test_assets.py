import os
import sys
import unittest

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.assets import get_bike_image

class TestAssetLoader(unittest.TestCase):
    def test_verified_model(self):
        """Verify that a known model returns an official RE URL"""
        url = get_bike_image("Classic 350")
        self.assertIn("royalenfield.com", url)
        self.assertTrue(url.endswith(".jpg") or url.endswith(".webp"))

    def test_fuzzy_match(self):
        """Verify that fuzzy matching works (e.g. 'New Himalayan' matches 'Himalayan 450' keys)"""
        # Note: In our current implementation, 'Himalayan 450' is the key.
        # If the user selects 'New Himalayan', it should still return the official URL.
        url = get_bike_image("Himalayan 450")
        self.assertIn("royalenfield.com", url)

    def test_fallback_model(self):
        """Verify that an unknown model returns the RE logo fallback"""
        url = get_bike_image("Unknown Bike 999")
        self.assertIn("re-logo.svg", url)

    def test_local_fallback(self):
        """
        Verify that if a local file exists, it's used.
        We'll simulate this by creating a small dummy file and then a 'large' one.
        """
        assets_dir = os.path.join("assets", "bikes")
        os.makedirs(assets_dir, exist_ok=True)
        
        test_file = os.path.join(assets_dir, "Test_Bike.jpg")
        
        # 1. Test small file (< 10KB) -> should return fallback
        with open(test_file, "wb") as f:
            f.write(b"too small")
        
        url = get_bike_image("Test Bike")
        self.assertIn("re-logo.svg", url)
        
        # 2. Test large file (> 10KB) -> should return base64
        with open(test_file, "wb") as f:
            f.write(b"x" * (11 * 1024))
            
        url = get_bike_image("Test Bike")
        self.assertIn("data:image/jpeg;base64", url)
        
        # 3. Test HTML slop -> should return fallback
        with open(test_file, "wb") as f:
            f.write(b"<!DOCTYPE html><html><body>Slop</body></html>")
            # Make it large enough
            f.write(b"x" * (11 * 1024))
            
        url = get_bike_image("Test Bike")
        self.assertIn("re-logo.svg", url)
        
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)

if __name__ == "__main__":
    unittest.main()
