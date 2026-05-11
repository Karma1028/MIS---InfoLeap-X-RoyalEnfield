import asyncio
from playwright.async_api import async_playwright
import os
import time

async def verify_showroom_layout():
    async with async_playwright() as p:
        # Launch browser in headed mode as requested
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Streamlit default port
        url = "http://localhost:8501"
        
        print(f"Connecting to {url}...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Wait for the custom ID to be present, indicating content rendering
            print("Waiting for #stage-01 to appear...")
            await page.wait_for_selector("#stage-01", timeout=30000)
            
            # 1. Verify Background Color
            # Sometimes Streamlit applies styles to a wrapper
            bg_color = await page.evaluate("""
                () => {
                    const el = document.querySelector('[data-testid="stAppViewContainer"]');
                    return window.getComputedStyle(el).backgroundColor;
                }
            """)
            print(f"Background Color (stAppViewContainer): {bg_color}")
            
            # If stAppViewContainer is transparent, check the main app container
            if bg_color == "rgba(0, 0, 0, 0)":
                bg_color = await page.evaluate("""
                    () => window.getComputedStyle(document.body).backgroundColor
                """)
                print(f"Background Color (body): {bg_color}")

            # 2. Verify Glass Card Blur on Parent
            blur_effect = await page.evaluate("""
                () => {
                    const stage = document.querySelector('#stage-01');
                    const container = stage.closest('[data-testid="stVerticalBlock"] > div');
                    return window.getComputedStyle(container).backdropFilter || window.getComputedStyle(container).webkitBackdropFilter;
                }
            """)
            print(f"Container Blur Effect: {blur_effect}")
            assert "blur(10px)" in blur_effect, f"Expected blur(10px), got {blur_effect}"
            
            # 3. Verify Stages exist
            for i in range(1, 5):
                stage_exists = await page.query_selector(f"#stage-0{i}")
                assert stage_exists is not None, f"Stage 0{i} not found"
                print(f"Stage 0{i} verified.")
            
            # 4. Capture screenshot
            screenshot_path = "tests/task1_showroom_layout.png"
            os.makedirs("tests", exist_ok=True)
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot saved to {screenshot_path}")
            
            print("Verification Successful!")
            
        except Exception as e:
            print(f"Verification Failed: {e}")
            # Take a failure screenshot
            await page.screenshot(path="tests/task1_failure.png")
            raise e
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(verify_showroom_layout())
