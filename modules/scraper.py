import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def scrape_fwa_details(clan_tag):
    """
    Asynchronously fetches and parses FWA details from the web page.
    Bypasses Playwright to prevent Cloudflare datacenter blocks on Render.
    """
    clean_tag = clan_tag.replace("#", "").strip()
    
    data = {
        "point_balance": "N/A",
        "war_id": "N/A",
        "sync_num": "N/A",
        "match_type": "Unknown"
    }

    url = f"https://points.fwafarm.com/clan?tag={clean_tag}"
    
    # Browser headers help bypass basic Cloudflare block strings on static pages
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=15) as response:
                if response.status != 200:
                    print(f"[Scraper Warning] Received status {response.status} for tag {clean_tag}")
                    return data
                
                html = await response.text()
                
                # Check if we got hit by an obvious Cloudflare challenge page
                if "cloudflare" in html.lower() and "captcha" in html.lower():
                    print(f"[Scraper Error] Cloudflare blocked the request on Render IP.")
                    data["match_type"] = "Blocked by Cloudflare"
                    return data

                # Parse layout text using BeautifulSoup (or manual split if bs4 isn't installed)
                # To ensure it runs without extra installs, we use manual text lines processing:
                clean_lines = [line.strip() for line in html.splitlines() if line.strip()]
                
                win_calculator_heading = ""
                match_status = ""
                
                for i, line in enumerate(clean_lines):
                    # Strip raw HTML tags for basic text matching
                    visible_line = ''.join(BeautifulSoup(line, "html.parser").stripped_strings) if "BeautifulSoup" in globals() else line
                    
                    if "Point Balance:" in visible_line:
                        try:
                            data["point_balance"] = visible_line.split("Point Balance:")[1].split("<")[0].strip()
                        except Exception: pass
                        
                    if "Win Calculator for" in visible_line:
                        win_calculator_heading = visible_line
                        # Look at subsequent lines for status
                        for offset in range(1, 5):
                            if i + offset < len(clean_lines):
                                test_line = clean_lines[i + offset]
                                if "points" in test_line.lower() or "match" in test_line.lower():
                                    match_status = test_line
                                    break
                
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

    except Exception as e:
        print(f"[Scraper Error] Unexpected issue fetching details: {e}")
        
    return data
