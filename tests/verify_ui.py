import subprocess
import time
import os
import signal
from playwright.sync_api import sync_playwright

def run_ui_test():
    # Start Streamlit in the background
    print("Starting Streamlit app...")
    process = subprocess.Popen(
        ["streamlit", "run", "app.py", "--server.port", "8502", "--server.headless", "true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )
    
    time.sleep(10) # Wait for Streamlit to start
    
    try:
        with sync_playwright() as p:
            # We use headless=False as requested, but since we are in a CLI, 
            # we might need to use a virtual display if available.
            # However, the prompt says "headed mode (headless=False)".
            # If it fails due to no display, I'll fallback to headless for the screenshot.
            try:
                browser = p.chromium.launch(headless=False)
            except Exception as e:
                print(f"Could not launch headed mode: {e}. Falling back to headless.")
                browser = p.chromium.launch(headless=True)
                
            page = browser.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            
            print("Navigating to app...")
            page.goto("http://localhost:8502")
            
            # Wait for the app to load
            page.wait_for_selector("text=ROYAL ENFIELD", timeout=30000)
            
            # Verify dark theme (background color of .stApp)
            # The CSS var --midnight-black is #1a1a1a
            bg_color = page.evaluate("window.getComputedStyle(document.querySelector('.stApp')).backgroundColor")
            print(f"Detected background color: {bg_color}")
            
            # #1a1a1a in RGB is rgb(26, 26, 26)
            assert "rgb(26, 26, 26)" in bg_color or "rgba(26, 26, 26" in bg_color, f"Background color should be #1a1a1a, got {bg_color}"
            
            # Take a screenshot
            screenshot_path = "dashboard_midnight_chrome.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot saved to {screenshot_path}")
            
            browser.close()
            print("UI Test Passed!")
            
    finally:
        print("Stopping Streamlit app...")
        if os.name == 'nt':
            subprocess.call(['taskkill', '/F', '/T', '/PID', str(process.pid)])
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)

if __name__ == "__main__":
    run_ui_test()
