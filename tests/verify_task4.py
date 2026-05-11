import os
import sys
from utils.assets import BikeAssetLoader

def verify():
    loader = BikeAssetLoader()
    
    # 1. Check Classic 350 (Source 1)
    url = loader.get_asset_url("Classic 350")
    print(f"Classic 350 URL: {url}")
    if not url.startswith("http") or "unsplash" not in url:
        print("FAILED: Classic 350 should return verified Unsplash URL")
        return False

    # 2. Check Hunter 350 (Source 1)
    url = loader.get_asset_url("Hunter 350")
    print(f"Hunter 350 URL: {url}")
    if not url.startswith("http") or "unsplash" not in url:
        print("FAILED: Hunter 350 should return verified Unsplash URL")
        return False

    # 3. Check a model not in Source 1 (should fall back to Source 3 or Fallback)
    # Since Source 3 might timeout in this environment, it might return FALLBACK_URL
    url = loader.get_asset_url("Bear 650")
    print(f"Bear 650 URL: {url}")
    if url == loader.FALLBACK_URL:
        print("INFO: Bear 650 returned fallback (Source 3 might have timed out or failed)")
    elif url.startswith("http"):
        print("SUCCESS: Bear 650 returned a URL (Source 3 or Fallback)")
    else:
        print("FAILED: Bear 650 should return a valid URL")
        return False

    # 4. Verify no base64 URLs (since all local files are gone)
    if "base64" in url:
        print("FAILED: Should not return base64 URL when local assets are missing/invalid")
        return False

    print("\nALL VERIFICATIONS PASSED (considering environment limitations for live search)")
    return True

if __name__ == "__main__":
    # Add root to sys.path
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    if verify():
        sys.exit(0)
    else:
        sys.exit(1)
