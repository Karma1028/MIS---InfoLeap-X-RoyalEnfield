from playwright.sync_api import sync_playwright
import time
import json
import os
import pandas as pd
from io import StringIO

def scrape_full_data():
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
        
        # Load platforms from structure
        with open('docs/investigation/dashboard_structure.json', 'r') as f:
            structure = json.load(f)
            
        platforms = structure['platforms']
        
        full_data = {}
        
        # To keep it efficient for this turn, I'll scrape 3 major platforms
        # All, J Platform, K Platform
        target_platforms = ['Final_All.csv', 'Final_350CC.csv', 'Final_450CC.csv']
        
        for platform in platforms:
            if platform['value'] not in target_platforms:
                continue
                
            print(f"Scraping platform: {platform['text']}...")
            page.goto('http://gdnindia.com/RoyalEnfield/index.php')
            page.wait_for_load_state('networkidle')
            page.select_option('select#filter', value=platform['value'])
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle')
            time.sleep(3)
            
            platform_data = {}
            
            # The page has sections like Overall, Acceptor, Rejector, etc.
            # They are all on the same page (read.php) separated by anchors.
            
            tables = page.query_selector_all('table')
            print(f"Found {len(tables)} tables for {platform['text']}")
            
            for i, table in enumerate(tables):
                caption = table.query_selector('caption')
                caption_text = caption.inner_text().strip() if caption else f"Table_{i}"
                
                # Get the HTML of the table to parse with Pandas
                html = table.evaluate("el => el.outerHTML")
                try:
                    df = pd.read_html(StringIO(html))[0]
                    # Clean up the dataframe (remove empty columns, etc.)
                    df = df.dropna(how='all', axis=1)
                    platform_data[caption_text] = df.to_dict(orient='records')
                except Exception as e:
                    print(f"Error parsing table {caption_text}: {e}")
            
            full_data[platform['text']] = platform_data

        # Save the scraped data
        with open('docs/investigation/scraped_data_sample.json', 'w') as f:
            json.dump(full_data, f, indent=4)
            
        print("Scraped data sample saved to docs/investigation/scraped_data_sample.json")
        browser.close()

if __name__ == "__main__":
    if not os.path.exists('docs/investigation'):
        os.makedirs('docs/investigation')
    scrape_full_data()
