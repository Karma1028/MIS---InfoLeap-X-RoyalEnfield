import asyncio
from playwright.async_api import async_playwright
import os

async def verify_dashboard():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) # Forced headless for CI, but simulation of headed
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        
        # Go to the app
        print("Navigating to http://localhost:8501...")
        await page.goto("http://localhost:8501", wait_until="networkidle")
        
        # Wait for charts to load (Plotly charts are in divs with class 'js-plotly-plot')
        print("Waiting for charts...")
        await page.wait_for_selector(".js-plotly-plot", timeout=30000)
        
        # Take a screenshot
        screenshot_path = "dashboard_charts_initial.png"
        await page.screenshot(path=screenshot_path)
        print(f"Initial screenshot saved to {screenshot_path}")
        
        # Change Platform in sidebar
        print("Changing platform in sidebar...")
        # Streamlit selectboxes are usually within 'stSelectbox' div
        await page.click('text=PLATFORM')
        await page.keyboard.press("ArrowDown")
        await page.keyboard.press("Enter")
        
        # Wait for re-render
        await asyncio.sleep(5)
        
        # Take another screenshot
        screenshot_path_updated = "dashboard_charts_updated.png"
        await page.screenshot(path=screenshot_path_updated)
        print(f"Updated screenshot saved to {screenshot_path_updated}")
        
        # Verify charts still exist
        chart_count = await page.locator(".js-plotly-plot").count()
        print(f"Found {chart_count} charts.")
        
        await browser.close()
        
        if chart_count >= 4:
            print("VERIFICATION SUCCESS: At least 4 interactive charts found.")
        else:
            print(f"VERIFICATION FAILURE: Only found {chart_count} charts.")

if __name__ == "__main__":
    asyncio.run(verify_dashboard())
