from playwright.sync_api import sync_playwright
import time
import json
import os

def deep_investigation():
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
        
        # 1. Map out all Platforms and Models
        platforms = []
        options = page.query_selector_all('select#filter option')
        for opt in options:
            val = opt.get_attribute('value')
            text = opt.inner_text().strip()
            if val and val != "Please":
                platforms.append({'value': val, 'text': text})
        
        models = []
        options = page.query_selector_all('select#items1 option')
        for opt in options:
            val = opt.get_attribute('value')
            text = opt.inner_text().strip()
            if val:
                models.append({'value': val, 'text': text})
        
        investigation_data = {
            'platforms': platforms,
            'models': models,
            'tabs': ['Overall', 'Acceptor', 'Rejector', 'Booked but Cancelled'],
            'views': []
        }
        
        print(f"Found {len(platforms)} platforms and {len(models)} models.")
        
        # 2. Explore "Overall" view for "All" platform
        print("Exploring 'Final_All.csv'...")
        page.select_option('select#filter', value='Final_All.csv')
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')
        time.sleep(3)
        
        # Map sections/tabs on the read.php page
        tabs = page.query_selector_all('.navbar-nav a')
        tab_names = [t.inner_text().strip() for t in tabs]
        print(f"Tabs found on results page: {tab_names}")
        
        # Capture structure of tables
        tables = page.query_selector_all('table')
        table_structures = []
        for i, table in enumerate(tables[:10]): # Sample first 10 tables
            caption = table.query_selector('caption')
            caption_text = caption.inner_text().strip() if caption else f"Table {i}"
            headers = [th.inner_text().strip() for th in table.query_selector_all('thead th')]
            # Get first row of data to see base
            first_row = [td.inner_text().strip() for td in table.query_selector_all('tbody tr:first-child td')]
            table_structures.append({
                'name': caption_text,
                'headers': headers,
                'sample_row': first_row
            })
        
        investigation_data['sample_tables'] = table_structures
        
        # Save results
        with open('docs/investigation/dashboard_structure.json', 'w') as f:
            json.dump(investigation_data, f, indent=4)
            
        # Capture specific metrics across multiple models to understand variances
        # We'll just take a few screenshots for visual reference
        samples_to_check = ['Final_All.csv', 'Final_350CC.csv', 'Final_Classic 350.csv']
        for sample in samples_to_check:
            page.goto('http://gdnindia.com/RoyalEnfield/index.php')
            page.wait_for_load_state('networkidle')
            page.select_option('select#filter', value=sample)
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
            page.screenshot(path=f'docs/investigation/view_{sample}.png', full_page=True)
            print(f"Captured screenshot for {sample}")

        browser.close()

if __name__ == "__main__":
    if not os.path.exists('docs/investigation'):
        os.makedirs('docs/investigation')
    deep_investigation()
