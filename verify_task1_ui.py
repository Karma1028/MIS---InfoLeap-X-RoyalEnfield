
import asyncio
from playwright.async_api import async_playwright
import os

async def capture_ui():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        try:
            print("Navigating to http://localhost:8501...")
            await page.goto("http://localhost:8501", timeout=60000)
            # Wait for streamlit to load
            await page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=30000)
            # Wait a bit more for charts to render
            await asyncio.sleep(10)
            
            screenshot_path = "tests/task1_verification.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"Screenshot saved to {screenshot_path}")
            
            # Verify background color
            bg_color = await page.evaluate("""
                window.getComputedStyle(document.querySelector('[data-testid="stAppViewContainer"]')).backgroundColor
            """)
            print(f"Background color: {bg_color}")
            
            # Check for stage IDs and their parents
            stages_info = await page.evaluate("""
                () => {
                    const ids = ['#stage-01', '#stage-02', '#stage-03', '#stage-04'];
                    return ids.map(id => {
                        const el = document.querySelector(id);
                        if (!el) return { id, found: false };
                        const parent = el.closest('div[data-testid="stVerticalBlock"] > div');
                        const style = parent ? window.getComputedStyle(parent) : null;
                        return {
                            id,
                            found: true,
                            parentFound: !!parent,
                            blur: style ? (style.backdropFilter || style.webkitBackdropFilter) : 'N/A',
                            bgColor: style ? style.backgroundColor : 'N/A'
                        };
                    });
                }
            """)
            for info in stages_info:
                print(f"Stage Info: {info}")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_ui())
