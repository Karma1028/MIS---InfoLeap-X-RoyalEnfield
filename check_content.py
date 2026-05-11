
import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('http://localhost:8505')
        await asyncio.sleep(10)
        
        # Check if element exists
        el = await page.query_selector('#stage-01')
        if el:
            print("ELEMENT #stage-01 FOUND")
            # Check parent style
            parent_style = await page.evaluate("""
                () => {
                    const el = document.querySelector('#stage-01');
                    const parent = el.closest('div[data-testid="stVerticalBlock"] > div');
                    if (!parent) return { error: 'Parent not found' };
                    const style = window.getComputedStyle(parent);
                    return {
                        blur: style.backdropFilter || style.webkitBackdropFilter,
                        bgColor: style.backgroundColor
                    };
                }
            """)
            print(f"Parent Style: {parent_style}")
            
            # Check app background
            app_bg = await page.evaluate("""
                () => {
                    const el = document.querySelector('[data-testid="stAppViewContainer"]');
                    const style = window.getComputedStyle(el);
                    return style.backgroundColor;
                }
            """)
            print(f"App Background: {app_bg}")
        else:
            print("ELEMENT #stage-01 NOT FOUND")
            # Print all IDs in the page to see what's there
            ids = await page.evaluate("() => Array.from(document.querySelectorAll('[id]')).map(el => el.id)")
            print(f"IDs found on page: {ids}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
