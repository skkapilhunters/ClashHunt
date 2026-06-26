import urllib.parse
import os
import subprocess
import sys
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def auto_install_playwright_browsers():
    """Checks if playwright binaries are missing and installs them automatically."""
    try:
        # Check if the browser executable exists or if we need to force install it
        with sync_playwright() as p:
            # We try a quick launch check to see if dependencies are configured
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception as e:
        # If it throws an error stating executable doesn't exist, execute automatic recovery
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e).lower():
            print("\n⚠️ [Playwright Boot] Headless browser binaries missing. Triggering automatic installation...")
            try:
                # Executes 'playwright install chromium' securely via system terminal environment
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"], 
                    check=True
                )
                print("✅ [Playwright Boot] Chromium dependencies installed successfully!\n")
            except Exception as install_error:
                print(f"❌ [Playwright Boot Error] Failed to run automated installation: {install_error}")
        else:
            # If it's a different runtime error, print it out so it doesn't stay hidden
            print(f"[Playwright Boot Warning] Checked system binaries, status: {e}")

def scrape_fwa_details(clan_tag):
    """
    SECONDARY UTILITY FUNCTION: 
    Scrapes FWA details for a specific clan tag and returns data to the main bot.
    """
    # 🔥 Run the automatic check and installation sequence before attempting to launch the browser
    auto_install_playwright_browsers()

    clean_tag = clan_tag.replace("#", "").strip()
    
    # Default fallback data if the site fails or times out
    data = {
        "point_balance": "N/A",
        "war_id": "N/A",
        "sync_num": "N/A",
        "match_type": "Unknown"
    }

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True) 
            page = browser.new_page()
            
            page.goto(f"https://points.fwafarm.com/clan?tag={clean_tag}", timeout=25000)
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
            elif "should win" in match_status or "points" in match_status:
                data["match_type"] = "FWA Match"
            else:
                data["match_type"] = "Verification Required"

        except PlaywrightTimeoutError:
            print(f"[Scraper Warning] Page timed out for tag {clean_tag}. Using fallbacks.")
        except Exception as e:
            print(f"[Scraper Error] Unexpected background issue: {e}")
        finally:
            try:
                browser.close()
            except Exception:
                pass
            
    return data

# Prevent direct execution from the terminal
if __name__ == "__main__":
    print("\n[!] This is a secondary utility module used by the Discord bot.")
    print("[!] To start the bot, run: python main.py\n")
