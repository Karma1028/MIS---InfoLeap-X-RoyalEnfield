import asyncio
from playwright.async_api import async_playwright
import os
import subprocess
import time

async def verify_dashboard():
    # Start streamlit in background
    proc = subprocess.Popen(["streamlit", "run", "app.py", "--server.port", "8502", "--server.headless", "true"])
    time.sleep(10) # Give it time to start

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})
            
            # Go to the app
            await page.goto("http://localhost:8502")
            
            # Wait for the dashboard to load (wait for the hero title)
            await page.wait_for_selector(".hero-title")
            
            # Wait for charts to render
            await page.wait_for_timeout(5000)
            
            # Take a screenshot
            await page.screenshot(path="dashboard_final_golden.png", full_page=True)
            print("Screenshot saved as dashboard_final_golden.png")
            
            # Verify some elements
            title = await page.inner_text(".hero-title")
            print(f"Verified Hero Title: {title}")
            
            metrics = await page.query_selector_all("[data-testid='stMetricValue']")
            print(f"Found {len(metrics)} metrics.")
            for i, m in enumerate(metrics):
                val = await m.inner_text()
                print(f"Metric {i+1} value: {val}")

            await browser.close()
    finally:
        proc.terminate()

if __name__ == "__main__":
    asyncio.run(verify_dashboard())
