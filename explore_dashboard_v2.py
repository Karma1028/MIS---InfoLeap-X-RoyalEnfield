from playwright.sync_api import sync_playwright
import time

def login_and_explore():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        url = 'http://gdnindia.com/RoyalEnfield/index.php'
        print(f'Attempting login at {url} with corrected credentials...')
        page.goto(url)
        page.wait_for_load_state('networkidle')
        
        # Fill corrected credentials
        page.fill('input[name="uname"]', 'misdashboard@infoleap')
        page.fill('input[name="pass"]', 'MIS_INFOLEAP@1234')
        
        print("Submitting...")
        page.click('button[name="loginSub"]')
        
        page.wait_for_load_state('networkidle')
        time.sleep(5) # Wait for dashboard to load
        
        final_url = page.url
        print(f"Final URL: {final_url}")
        
        page.screenshot(path='dashboard_success.png', full_page=True)
        
        content = page.content()
        if "Wrong!" in content:
            print("Login failed again. Check credentials.")
        else:
            print("Login successful! Saving content...")
            with open('dashboard_main.html', 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Extract links to other dashboard pages
            links = page.query_selector_all('a')
            print(f"Found {len(links)} links. Exploring...")
            for i, link in enumerate(links):
                href = link.get_attribute('href')
                text = link.inner_text().strip()
                if href and not href.startswith('#') and 'logout' not in href.lower() and href != 'index.php':
                    print(f"Navigating to {text} ({href})...")
                    # Open in a new page to keep main dashboard open if needed
                    new_page = browser.new_page()
                    try:
                        # Construct absolute URL if needed
                        target_url = href if href.startswith('http') else f"http://gdnindia.com/RoyalEnfield/{href}"
                        new_page.goto(target_url)
                        new_page.wait_for_load_state('networkidle')
                        time.sleep(2)
                        sanitized_text = "".join([c for c in text if c.isalnum() or c==' ']).rstrip()
                        new_page.screenshot(path=f'page_{i}_{sanitized_text}.png', full_page=True)
                        with open(f'page_{i}_{sanitized_text}.html', 'w', encoding='utf-8') as f:
                            f.write(new_page.content())
                        print(f"Captured {text}")
                    except Exception as e:
                        print(f"Failed to capture {text}: {e}")
                    new_page.close()

        browser.close()

if __name__ == "__main__":
    login_and_explore()
