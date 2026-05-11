from playwright.sync_api import sync_playwright
import time
import os

def explore():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        url = 'http://gdnindia.com/RoyalEnfield/index.php'
        print(f'Navigating to {url}...')
        page.goto(url)
        page.wait_for_load_state('networkidle')
        
        page.screenshot(path='login_page.png')
        print('Screenshot saved as login_page.png')
        
        # Log in
        # Based on typical index.php login pages, let's look for common names
        # We'll use the HTML we're about to save to be sure, but let's try some common ones first
        
        username = 'misdashboard'
        password = 'MIS_INFOLEAP'
        
        try:
            # Try to find input fields by common attributes
            user_field = page.locator('input[name*="user" i], input[name*="name" i], input[type="text"]')
            pass_field = page.locator('input[name*="pass" i], input[type="password"]')
            submit_button = page.locator('input[type="submit"], button[type="submit"], button:has-text("Login"), input:has-text("Login")')
            
            if user_field.count() > 0:
                user_field.first.fill(username)
                print("Filled username")
            if pass_field.count() > 0:
                pass_field.first.fill(password)
                print("Filled password")
            
            if submit_button.count() > 0:
                submit_button.first.click()
                print("Clicked login")
            else:
                # Try pressing enter
                page.keyboard.press("Enter")
                print("Pressed Enter to login")
                
            page.wait_for_load_state('networkidle')
            time.sleep(2) # Extra wait for any redirects
            
            page.screenshot(path='dashboard_main.png')
            print('Screenshot saved as dashboard_main.png')
            
            with open('dashboard_main.html', 'w', encoding='utf-8') as f:
                f.write(page.content())
            print('HTML saved as dashboard_main.html')
            
            # Extract links to other pages
            links = page.locator('a').all()
            print(f"Found {len(links)} links on main dashboard")
            for i, link in enumerate(links[:20]): # Show first 20
                try:
                    text = link.inner_text().strip()
                    href = link.get_attribute('href')
                    if href and not href.startswith('#') and 'logout' not in href.lower():
                        print(f"Link {i}: {text} -> {href}")
                except:
                    pass

        except Exception as e:
            print(f"Error during exploration: {e}")
            page.screenshot(path='error_state.png')
        
        browser.close()

if __name__ == "__main__":
    explore()
