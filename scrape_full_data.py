from playwright.sync_api import sync_playwright
import time
import json
import os
import pandas as pd
from io import StringIO

def scrape_full_data():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Increase timeout for slow page loads
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        url = 'http://gdnindia.com/RoyalEnfield/index.php'
        
        print(f'Logging in at {url}...')
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state('networkidle')
            
            # Login
            page.fill('input[name="uname"]', 'misdashboard@infoleap')
            page.fill('input[name="pass"]', 'MIS_INFOLEAP@1234')
            page.click('button[name="loginSub"]')
            page.wait_for_load_state('networkidle')
            time.sleep(2)
        except Exception as e:
            print(f"Login failed: {e}")
            browser.close()
            return

        # Load platforms from structure
        structure_path = 'docs/investigation/dashboard_structure.json'
        if not os.path.exists(structure_path):
            print(f"Structure file not found: {structure_path}")
            browser.close()
            return
            
        with open(structure_path, 'r') as f:
            structure = json.load(f)
            
        platforms = structure['platforms']
        full_results = {}
        total_combinations = 0
        total_tables = 0

        for platform in platforms:
            platform_value = platform['value']
            platform_text = platform['text'].strip()
            
            print(f"\n--- Processing Platform: {platform_text} ---")
            
            # Go back to index to reset filters
            page.goto('http://gdnindia.com/RoyalEnfield/index.php')
            page.wait_for_load_state('networkidle')
            
            # Select platform
            page.select_option('select#filter', value=platform_value)
            time.sleep(1) # Let JS update models
            
            # Get visible models
            model_options = page.query_selector_all('select#items1 option')
            visible_models = []
            for opt in model_options:
                is_visible = opt.evaluate("el => el.style.display !== 'none'")
                if is_visible:
                    visible_models.append({
                        'value': opt.get_attribute('value'),
                        'text': opt.inner_text().strip()
                    })
            
            print(f"Found {len(visible_models)} visible models for {platform_text}")
            
            for model in visible_models:
                model_value = model['value']
                model_text = model['text']
                combo_key = f"{platform_text} | {model_text}"
                
                print(f"  Scraping combination: {combo_key}...")
                
                # Re-select platform (just in case) and select model
                page.select_option('select#filter', value=platform_value)
                page.select_option('select#items1', value=model_value)
                
                # Submit form
                # Use click on the submit button
                page.click('button[type="submit"]')
                
                try:
                    # Wait for results page (read.php)
                    page.wait_for_load_state('networkidle', timeout=30000)
                    time.sleep(2) # Extra wait for dynamic tables if any
                    
                    # Check if we are on read.php
                    if 'read.php' not in page.url:
                        print(f"    Warning: Expected read.php but got {page.url}")
                    
                    # Extract all tables
                    tables_data = {}
                    tables = page.query_selector_all('table')
                    
                    # Sections help to categorize tables
                    # We can find headers (h3, h4) preceding tables to give them better names
                    
                    for i, table in enumerate(tables):
                        # Try to find caption
                        caption = table.query_selector('caption')
                        if caption:
                            caption_text = caption.inner_text().strip()
                        else:
                            # Try to find preceding h4 or h3
                            # This is a bit complex in Playwright, so we'll use a fallback
                            caption_text = f"Table_{i}"
                        
                        # Handle duplicate caption names
                        orig_caption = caption_text
                        counter = 1
                        while caption_text in tables_data:
                            caption_text = f"{orig_caption}_{counter}"
                            counter += 1

                        html = table.evaluate("el => el.outerHTML")
                        try:
                            # Use Pandas to parse table
                            df_list = pd.read_html(StringIO(html))
                            if df_list:
                                df = df_list[0]
                                # Basic cleaning
                                df = df.fillna("")
                                # If the table has a multi-index header (like in the HTML we saw)
                                # Pandas might handle it well or need flattening
                                tables_data[caption_text] = df.to_dict(orient='records')
                                total_tables += 1
                        except Exception as e:
                            print(f"      Error parsing table {caption_text}: {e}")
                    
                    full_results[combo_key] = tables_data
                    total_combinations += 1
                    print(f"    Captured {len(tables_data)} tables.")
                    
                    # Go back to index for next model
                    # Or we can just use page.goto(url)
                    page.goto(url)
                    page.wait_for_load_state('networkidle')
                    
                except Exception as e:
                    print(f"    Error scraping {combo_key}: {e}")
                    page.goto(url)
                    page.wait_for_load_state('networkidle')

        # Save final result
        output_path = 'docs/investigation/full_scraped_data.json'
        with open(output_path, 'w') as f:
            json.dump(full_results, f, indent=4)
            
        print(f"\nScraping complete!")
        print(f"Total combinations scraped: {total_combinations}")
        print(f"Total tables extracted: {total_tables}")
        print(f"Results saved to {output_path}")
        
        browser.close()

if __name__ == "__main__":
    if not os.path.exists('docs/investigation'):
        os.makedirs('docs/investigation')
    scrape_full_data()
