from playwright.sync_api import sync_playwright
import time

def login_attempt():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        url = 'http://gdnindia.com/RoyalEnfield/index.php'
        print(f'Attempting login at {url}...')
        page.goto(url)
        page.wait_for_load_state('networkidle')
        
        # Use exact selectors from the HTML source
        page.fill('input[name="uname"]', 'misdashboard')
        page.fill('input[name="pass"]', 'MIS_INFOLEAP')
        
        print("Filled uname and pass. Submitting...")
        page.click('button[name="loginSub"]')
        
        page.wait_for_load_state('networkidle')
        time.sleep(3) # Wait for potential redirect
        
        final_url = page.url
        print(f"Final URL: {final_url}")
        
        page.screenshot(path='login_result_precise.png')
        
        content = page.content()
        if "Wrong!" in content:
            print("Login failed: 'Wrong!' message detected.")
        elif "Dashboard" in content or "index.php" not in final_url:
            print("Login potentially successful!")
            with open('dashboard_content.html', 'w', encoding='utf-8') as f:
                f.write(content)
        else:
            print("Login status unclear. Check login_result_precise.png")
            with open('login_result_precise.html', 'w', encoding='utf-8') as f:
                f.write(content)
                
        browser.close()

if __name__ == "__main__":
    login_attempt()
