import re
from playwright.sync_api import Playwright, sync_playwright, expect
import time
import subprocess
import os
import signal

def run(playwright: Playwright) -> None:
    # Start Streamlit in the background
    # We use a different port to avoid conflicts
    port = "8502"
    process = subprocess.Popen(
        ["streamlit", "run", "app.py", "--server.port", port, "--server.headless", "true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid if hasattr(os, 'setsid') else None
    )
    
    time.sleep(10) # Wait for Streamlit to start
    
    try:
        browser = playwright.chromium.launch(headless=True) # Set to False for local headed mode if needed
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"http://localhost:{port}")

        # Wait for the dashboard to load
        page.wait_for_selector("h1.hero-title", timeout=30000)
        
        # Wait for charts to be rendered (Plotly charts have class 'js-plotly-plot')
        page.wait_for_selector(".js-plotly-plot", timeout=30000)
        time.sleep(5) # Give extra time for all 4 charts

        # Check for the 4 "Analyze" expanders
        # In Streamlit, expanders often use <div> with 'stExpander' in class or similar
        # But looking for text "Analyze" is generally okay if they are rendered
        expanders = page.get_by_text(re.compile(r"Analyze", re.IGNORECASE))
        
        # Take a screenshot for debugging if it fails
        page.screenshot(path="debug_ui.png")
        
        count = expanders.count()
        print(f"Found {count} elements with 'Analyze' text.")
        
        # If it still finds 1, maybe it's because they have the same text and get_by_text matches multiple?
        # Actually count() should return total.
        
        assert count >= 4, f"Expected at least 4 'Analyze' expanders, found {count}. See debug_ui.png"

        # Click the first one
        expanders.first.click()
        time.sleep(2)
        
        # Verify Persona selectbox label exists (using first to avoid strict mode violation)
        expect(page.get_by_text("Persona").first).to_be_visible()
        
        # Verify "Generate Insight" button exists
        btn = page.get_by_role("button", name="Generate Insight")
        expect(btn.first).to_be_visible()
        
        print("UI Integration Verified Successfully!")

        # ---------------------
        context.close()
        browser.close()
    finally:
        # Kill the Streamlit process
        if hasattr(os, 'killpg'):
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        else:
            process.terminate()

with sync_playwright() as playwright:
    run(playwright)
