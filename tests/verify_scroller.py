import time
import asyncio
from playwright.async_api import async_playwright

async def run_verification():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Start streamlit in the background if not already running
        # Assuming it's already running on localhost:8507 for this test
        try:
            await page.goto("http://localhost:8507")
            # Wait for app to load - Streamlit specific wait
            await page.wait_for_selector('div[data-testid="stSidebar"]', timeout=60000)
        except Exception as e:
            await page.screenshot(path="debug_timeout.png")
            print(f"Error during page load: {e}")
            raise e
        time.sleep(5) # Give it extra time to render main content
        
        print("Page loaded. Current scroll position:", await page.evaluate("window.scrollY"))
        
        # Select a different model to trigger scroll
        # Find the model selectbox
        await page.click('div[data-testid="stSidebar"] div[data-testid="stSelectbox"] >> nth=1')
        
        # Wait for options to appear and click one (e.g., the second one)
        # Note: nth=1 is the model selectbox, nth=0 is platform
        options = page.locator('ul[data-testid="stSelectboxVirtualList"] li')
        await options.nth(1).click()
        
        print("Model changed. Monitoring scroll position...")
        
        # Monitor scroll position for 5 seconds
        scroll_positions = []
        for _ in range(50): # 5 seconds, 100ms intervals
            pos = await page.evaluate("window.scrollY")
            scroll_positions.append(pos)
            await asyncio.sleep(0.1)
        
        print("Scroll positions log:", scroll_positions)
        
        # Verify scroll happened
        start_pos = scroll_positions[0]
        max_pos = max(scroll_positions)
        
        if max_pos > start_pos:
            print(f"SUCCESS: Auto-scroll detected! Max scroll position: {max_pos}")
        else:
            print("FAILURE: No auto-scroll detected.")
            
        # Check if it was smooth (multiple intermediate positions)
        unique_positions = len(set(scroll_positions))
        if unique_positions > 5:
            print(f"SUCCESS: Smooth scroll detected! ({unique_positions} unique positions)")
        else:
            print(f"FAILURE: Scroll might have been instant or didn't happen. ({unique_positions} unique positions)")

        await browser.close()

if __name__ == "__main__":
    import os
    # We need to run streamlit in background if we want to test
    # But usually the environment should have it running or we just run the verification
    # I'll try to run it assuming it might need a server
    asyncio.run(run_verification())
