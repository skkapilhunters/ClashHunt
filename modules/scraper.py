import os
import urllib.parse
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

load_dotenv()

def scrape_fwa_details(clan_tag):
    """
    Scrapes FWA details using Playwright routed through a Proxy server
    to bypass Cloudflare block screens on Render.
    """
    clean_tag = clan_tag.replace("#", "").strip()
    proxy_url = os.getenv("PROXY_URL")
    
    data = {
        "point_balance": "N/A",
        "war_id": "N/A",
        "sync_num": "N/A",
        "match_type": "Unknown"
    }

    # Configure Playwright proxy dictionary if PROXY_URL is present
    playwright_proxy = None
    if proxy_url:
        try:
            parsed = urllib.parse.urlparse(proxy_url)
            playwright_proxy = {
                "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
            }
            if parsed.username and parsed.password:
                playwright_proxy["username"] = parsed.username
                playwright_proxy["password"] = parsed.password
        except Exception as e:
            print(f"[Proxy Configuration Error] Could not parse PROXY_URL: {e}")

    browser = None
    try:
        with sync_playwright() as p:
            # Launch using your proxy settings
            launch_args = {"headless": True}
            if playwright_proxy:
                launch_args["proxy"] = playwright_proxy
                print(f"[Scraper] Routing Playwright request through proxy server...")
            else:
                print(f"[Scraper Warning] No PROXY_URL found in env. Running direct connection.")

            browser = p.chromium.launch(**launch_args) 
            
            # Mask the browser finger-print with standard window dimensions and a proper user-agent
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            
            page = context.new_page()
            
            # Navigate to the target page with an explicit 30-second timeout configuration
            page.goto(f"https://points.fwafarm.com/clan?tag={clean_tag}", timeout=30000)
            page.wait_for_load_state("networkidle")
            
            body_text = page.locator("body").inner_text()
            clean_lines = [line.strip() for line in body_text.split("\n") if line.strip()]
            
            win_calculator_heading = ""
            match_status = ""
            
            for i, line in enumerate(clean_lines):
                if "Point Balance:" in line:
                    data["point_balance"] = line.split(":", 1)[1].strip()
                    
                if "Win Calculator for" in line:
                    win_calculator_heading = line
                    if i + 2 < len(clean_lines):
                        match_status = clean_lines[i + 2]
            
            # Parse War ID & Sync Number
            if "War #" in win_calculator_heading:
                try:
                    data["war_id"] = win_calculator_heading.split("War #")[1].split(" ")[0].strip()
                except Exception: pass
            if "Sync #" in win_calculator_heading:
                try:
                    data["sync_num"] = win_calculator_heading.split("Sync #")[1].split(" ")[0].strip()
                except Exception: pass

            # Calculate Match Type
            if "Not marked as an FWA match" in match_status:
                data["match_type"] = "Mismatch"
            elif "should win" in match_status.lower() or "points" in match_status.lower():
                data["match_type"] = "FWA Match"
            else:
                data["match_type"] = "Verification Required"

    except PlaywrightTimeoutError:
        print(f"[Scraper Warning] Page timed out for tag {clean_tag}. The proxy may be slow or blocked.")
    except Exception as e:
        print(f"[Scraper Error] Unexpected background issue: {e}")
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
            
    return data

if __name__ == "__main__":
    print("\n[!] This is a secondary utility module used by the Discord bot.")
    print("[!] To start the bot, run: python main.py\n")
