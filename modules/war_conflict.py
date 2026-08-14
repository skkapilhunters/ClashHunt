import asyncio
import aiohttp
from datetime import datetime, timezone
import os

# Import your web scraper from modules
from modules.scraper import scrape_fwa_details

# Import Firebase exporter module
from modules.firebase_exporter import export_war_to_firebase

# UPDATED: New Supabase API Gateway
BASE_GATEWAY = "https://otbsecnrlgkpmomgwrtx.supabase.co/functions/v1/coc-api"

def normalize_tag(tag: str) -> str:
    """Normalizes Clash of Clans tags."""
    if not tag:
        return ""
    tag = tag.strip().upper()
    if not tag.startswith("#"):
        tag = "#" + tag
    return tag

def format_time(time_str: str) -> str:
    """Formats ISO API timestamps to YYYY-MM-DD HH:MM:SS."""
    if not time_str or time_str == "N/A":
        return "N/A"
    if "T" in time_str:
        try:
            clean = time_str.replace(".000Z", "").replace("Z", "")
            date_part, time_part = clean.split("T")
            formatted_date = f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"
            formatted_time = f"{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}"
            return f"{formatted_date} {formatted_time}"
        except Exception:
            return time_str
    return time_str

def format_attacks_list(member: dict, add_percent_sign: bool = True) -> list:
    """Formats member attack logs."""
    attacks = member.get("attacks", [])
    if not attacks:
        return []

    formatted_attacks = []
    for att in attacks:
        stars = att.get("stars", 0)
        dest = att.get("destructionPercentage", 0)
        order = att.get("order", "?")
        if add_percent_sign:
            formatted_attacks.append(f"Hit #{order}: {stars} stars {dest}%")
        else:
            formatted_attacks.append(f"Hit #{order}: {stars} stars {dest}")

    return formatted_attacks

def build_war_json(war_data: dict) -> dict:
    """Builds the structured conflict JSON payload."""
    if not war_data or war_data.get("state") == "notInWar":
        return {}

    state_map = {
        "preparation": "Preparation Day",
        "inWar": "Battle Day",
        "warEnded": "War Ended"
    }

    clan_a = war_data.get("clan", {})
    clan_b = war_data.get("opponent", {})

    clan_a_members = sorted(clan_a.get("members", []), key=lambda x: x.get("mapPosition", 99))
    clan_b_members = sorted(clan_b.get("members", []), key=lambda x: x.get("mapPosition", 99))

    team_size = max(len(clan_a_members), len(clan_b_members), war_data.get("teamSize", 0))

    war_metadata = {
        "prep_day_start": format_time(war_data.get("preparationStartTime", "N/A")),
        "battle_day_start": format_time(war_data.get("startTime", "N/A")),
        "war_ends": format_time(war_data.get("endTime", "N/A")),
        "status": state_map.get(war_data.get("state"), war_data.get("state", "Unknown")),
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    }

    clans = {
        "clan_a": {
            "name": clan_a.get("name", "Clan A"),
            "tag": normalize_tag(clan_a.get("tag", "")),
            "level": clan_a.get("clanLevel", 0),
            "type": "Official FWA",
            "members_count": clan_a.get("teamSize", team_size),
            "stars": clan_a.get("stars", 0),
            "destruction_percentage": f"{clan_a.get('destructionPercentage', 0)}%",
            "attacks_used": clan_a.get("attacks", 0)
        },
        "clan_b": {
            "name": clan_b.get("name", "Clan B"),
            "tag": normalize_tag(clan_b.get("tag", "")),
            "level": clan_b.get("clanLevel", 0),
            "type": "Official FWA",
            "members_count": clan_b.get("teamSize", team_size),
            "stars": clan_b.get("stars", 0),
            "destruction_percentage": f"{clan_b.get('destructionPercentage', 0)}%",
            "attacks_used": clan_b.get("attacks", 0)
        }
    }

    rosters = []
    for i in range(team_size):
        pos_num = i + 1

        if i < len(clan_a_members):
            m_a = clan_a_members[i]
            clan_a_member = {
                "name": m_a.get("name", "Unknown"),
                "tag": normalize_tag(m_a.get("tag", "")),
                "attacks": format_attacks_list(m_a, add_percent_sign=True)
            }
        else:
            clan_a_member = {"name": "Empty Slot", "tag": "", "attacks": []}

        if i < len(clan_b_members):
            m_b = clan_b_members[i]
            clan_b_member = {
                "name": m_b.get("name", "Unknown"),
                "tag": normalize_tag(m_b.get("tag", "")),
                "attacks": format_attacks_list(m_b, add_percent_sign=False)
            }
        else:
            clan_b_member = {"name": "Empty Slot", "tag": "", "attacks": []}

        rosters.append({
            "position": pos_num,
            "clan_a_member": clan_a_member,
            "clan_b_member": clan_b_member
        })

    return {
        "war_metadata": war_metadata,
        "clans": clans,
        "rosters": rosters
    }

async def generate_and_store_war_conflict(clan_tag: str, guild_id: int, db_collection) -> tuple[dict | None, str | None]:
    """
    Main function called by WarTracker:
    1. Fetches live CoC API war data using the new Supabase endpoint
    2. Runs Web Scraper & builds conflict JSON payload
    3. IF 'War Ended': Exports to Firebase & DELETES entry from MongoDB
    4. ELSE (ongoing war): Upserts payload into MongoDB
    """
    clean_tag = normalize_tag(clan_tag)
    
    # UPDATED: New payload structure for POST request
    payload = {
        "action": "current_war",
        "tag": clean_tag
    }

    async with aiohttp.ClientSession() as session:
        # UPDATED: Sending a POST request with JSON body and headers
        async with session.post(BASE_GATEWAY, json=payload, headers={'Content-Type': 'application/json'}) as response:
            if response.status != 200:
                return None, f"Proxy error HTTP {response.status}"
            raw_response = await response.json()
            
            # UPDATED: Replicating the JS extractData logic to handle nested Supabase responses
            war_data = raw_response.get("war") or raw_response.get("currentWar") or raw_response.get("data") or raw_response

    if war_data.get("state") == "notInWar":
        return None, "notInWar"

    # Run Playwright FWA web scraper asynchronously
    fwa_metrics = await asyncio.to_thread(scrape_fwa_details, clean_tag)

    # Build custom JSON structure
    conflict_json = build_war_json(war_data)

    if conflict_json and fwa_metrics:
        conflict_json["clans"]["clan_a"]["type"] = fwa_metrics.get("match_type", "Official FWA")

    current_status = conflict_json["war_metadata"]["status"]

    # 1. Automatic Migration & Cleanup if War Ended
    if current_status == "War Ended":
        # Export to Firebase Firestore
        migration_success = await export_war_to_firebase(clean_tag, guild_id, conflict_json)
        
        # Remove from MongoDB only if Firebase export was successful
        if migration_success:
            await db_collection.delete_one({"clan_tag": clean_tag, "guild_id": guild_id})
            print(f"🧹 [MongoDB Clean] Successfully moved ended war for {clean_tag} to Firebase and removed from MongoDB.")
        
        return conflict_json, None

    # 2. Store/Update ongoing war in MongoDB (Preparation Day / Battle Day)
    await db_collection.update_one(
        {"clan_tag": clean_tag, "guild_id": guild_id},
        {"$set": {
            "clan_tag": clean_tag,
            "guild_id": guild_id,
            "last_status": current_status,
            "conflict_data": conflict_json
        }},
        upsert=True
    )

    print(f"[WarConflict] Saved ongoing conflict payload for {clean_tag} in MongoDB (State: {current_status})")
    return conflict_json, None
