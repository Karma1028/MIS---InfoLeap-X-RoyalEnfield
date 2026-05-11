import os
import base64
import random
import time
from playwright.sync_api import sync_playwright

class BikeAssetLoader:
    VERIFIED_URLS = {
        "Classic 350": "https://images.unsplash.com/photo-1635073910831-24831856e1d4?auto=format&fit=crop&w=1350&q=80",
        "Himalayan 450": "https://images.unsplash.com/photo-1599819811279-d5ad9cccf838?auto=format&fit=crop&w=1350&q=80",
        "Interceptor 650": "https://images.unsplash.com/photo-1558981403-c5f91bbde3c0?auto=format&fit=crop&w=1350&q=80",
        "Continental GT 650": "https://images.unsplash.com/photo-1609630875171-b132112ee448?auto=format&fit=crop&w=1350&q=80",
        "Meteor 350": "https://images.unsplash.com/photo-1621360241119-c7520185ad5b?auto=format&fit=crop&w=1350&q=80",
        "Hunter 350": "https://images.unsplash.com/photo-1663162002573-04419996d9cc?auto=format&fit=crop&w=1350&q=80"
    }

    FALLBACK_URL = "https://images.unsplash.com/photo-1558981403-c5f91bbde3c0?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80"

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]

    def __init__(self):
        self.assets_path = os.path.join("assets", "bikes")

    def get_asset_url(self, model_name):
        # Source 1: Verified URLs
        if model_name in self.VERIFIED_URLS:
            return self.VERIFIED_URLS[model_name]

        # Source 2: Local Assets
        local_url = self._get_local_asset(model_name)
        if local_url:
            return local_url

        # Source 3: Headless Search
        search_url = self._search_fallback(model_name)
        if search_url:
            return search_url

        return self.FALLBACK_URL

    def _get_local_asset(self, model_name):
        filename = f"{model_name.replace(' ', '_')}.jpg"
        filepath = os.path.join(self.assets_path, filename)

        if not os.path.exists(filepath):
            return None

        # Check if it's over 50KB
        if os.path.getsize(filepath) < 50 * 1024:
            return None

        # Check if it's actually HTML
        try:
            with open(filepath, 'rb') as f:
                header = f.read(100)
                if b'<!DOCTYPE' in header or b'<html' in header:
                    return None
        except:
            return None

        # Return as base64
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
                return f"data:image/jpg;base64,{base64.b64encode(data).decode()}"
        except:
            return None

    def _search_fallback(self, model_name):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=random.choice(self.USER_AGENTS))
                page = context.new_page()
                
                # Search DuckDuckGo for images
                search_query = f"Royal Enfield {model_name} high resolution wallpaper"
                page.goto(f"https://duckduckgo.com/?q={search_query.replace(' ', '+')}&iax=images&ia=images")
                
                # Wait for images to load
                page.wait_for_selector(".tile--img__img", timeout=5000)
                
                # Get the first image URL
                img_element = page.query_selector(".tile--img__img")
                if img_element:
                    img_url = img_element.get_attribute("src")
                    if img_url and img_url.startswith("//"):
                        img_url = "https:" + img_url
                    
                    # Add a random delay to seem more human
                    time.sleep(random.uniform(0.5, 1.5))
                    
                    browser.close()
                    return img_url
                
                browser.close()
        except Exception as e:
            print(f"Search fallback failed for {model_name}: {e}")
        
        return None
