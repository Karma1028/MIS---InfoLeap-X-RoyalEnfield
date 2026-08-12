from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1700, "height": 1400})
    pg.goto("http://localhost:8502", timeout=30000)
    pg.wait_for_timeout(3000)

    # Click Model Comparison in sidebar
    pg.click('text=📊 Model Comparison')
    pg.wait_for_timeout(4000)

    pg.screenshot(path="docs/memory/model_comparison_10out10.png", full_page=False)
    print("Screenshot saved to docs/memory/model_comparison_10out10.png")
    b.close()
