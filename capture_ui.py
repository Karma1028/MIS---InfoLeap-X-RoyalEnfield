from playwright.sync_api import sync_playwright
import time
import subprocess
import os
import signal

def capture_ui():
    port = "8505"
    print(f"Starting Streamlit on port {port}...")
    
    # Use shell=True for windows to ensure streamlit is found in PATH
    process = subprocess.Popen(
        ["streamlit", "run", "app.py", "--server.port", port, "--server.headless", "true"],
        shell=True
    )
    
    time.sleep(20) # Significant wait for Streamlit startup and data loading
    
    try:
        with sync_playwright() as p:
            print("Launching browser...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            
            print(f"Navigating to http://localhost:{port}...")
            page.goto(f"http://localhost:{port}")
            
            # Wait for the app container
            page.wait_for_selector('div[data-testid="stAppViewContainer"]', timeout=60000)
            print("App container found. Waiting for charts to render...")
            
            time.sleep(10) # Wait for Plotly animations to finish
            
            page.screenshot(path="dashboard_ui_final.png", full_page=True)
            print("Screenshot saved as dashboard_ui_final.png")
            
            browser.close()
    except Exception as e:
        print(f"Error during capture: {e}")
    finally:
        print("Stopping Streamlit...")
        # On Windows, we might need to kill the process tree
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)

if __name__ == "__main__":
    capture_ui()
