from playwright.sync_api import sync_playwright
import time

def submit_dashboard():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        url = 'http://gdnindia.com/RoyalEnfield/index.php'
        print(f'Logging in at {url}...')
        page.goto(url)
        page.wait_for_load_state('networkidle')
        
        # Login
        page.fill('input[name="uname"]', 'misdashboard@infoleap')
        page.fill('input[name="pass"]', 'MIS_INFOLEAP@1234')
        page.click('button[name="loginSub"]')
        page.wait_for_load_state('networkidle')
        time.sleep(2)
        
        print("Selecting 'Final' and 'All'...")
        # Category is hidden but let's try to set it if needed
        # It seems Final is the only option
        
        # Platform/Filter: Select 'All'
        # <option class="Final" value="Final_All.csv"> All </option>
        page.select_option('select#filter', value='Final_All.csv')
        
        print("Submitting form...")
        # The submit button is in the center div
        page.click('button[type="submit"]')
        
        page.wait_for_load_state('networkidle')
        time.sleep(5) # Wait for charts to render
        
        print(f"URL after submit: {page.url}")
        page.screenshot(path='dashboard_view_all.png', full_page=True)
        
        with open('dashboard_view_all.html', 'w', encoding='utf-8') as f:
            f.write(page.content())
        
        # Let's see if there are iframes or charts
        print("Scanning for charts or data tables...")
        iframes = page.query_selector_all('iframe')
        print(f"Found {len(iframes)} iframes")
        for i, iframe in enumerate(iframes):
            src = iframe.get_attribute('src')
            print(f"Iframe {i} src: {src}")
            
        canvas_elements = page.query_selector_all('canvas')
        print(f"Found {len(canvas_elements)} canvas elements (potential charts)")
        
        tables = page.query_selector_all('table')
        print(f"Found {len(tables)} tables")

        browser.close()

if __name__ == "__main__":
    submit_dashboard()
