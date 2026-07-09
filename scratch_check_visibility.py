import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 1000}
        )
        page = context.new_page()
        
        try:
            page.goto("https://collegedunia.com/college/10343-christian-medical-college-cmc-vellore/courses-fees", timeout=60000)
            page.wait_for_timeout(4000)
            
            # Print page height
            scroll_height = page.evaluate("document.body.scrollHeight")
            print("Page Scroll Height:", scroll_height)
            
            # Let's locate the page 2 bubble
            page2_btn = page.locator("div.bubble:has-text('2')").first
            if page2_btn.count() > 0:
                print("Page 2 button count:", page2_btn.count())
                print("  is_visible:", page2_btn.is_visible())
                print("  is_enabled:", page2_btn.is_enabled())
                print("  bounding_box:", page2_btn.bounding_box())
                
                # Let's check its parent visibility
                parent = page2_btn.locator("xpath=..")
                print("  parent tag:", parent.evaluate("node => node.tagName"))
                print("  parent class:", parent.get_attribute("class"))
                print("  parent is_visible:", parent.is_visible())
                print("  parent bounding_box:", parent.bounding_box())
                
                # Check grandparents
                gparent = parent.locator("xpath=..")
                print("  grandparent tag:", gparent.evaluate("node => node.tagName"))
                print("  grandparent class:", gparent.get_attribute("class"))
                print("  grandparent is_visible:", gparent.is_visible())
                print("  grandparent bounding_box:", gparent.bounding_box())
            else:
                print("Page 2 bubble not found!")
                
        except Exception as e:
            print("Error:", e)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
