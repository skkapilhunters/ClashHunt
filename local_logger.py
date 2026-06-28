import sys
import json
import os
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient  # 👈 Added MongoDB client

# 🛠️ MongoDB Configuration
# Replace this connection string with your actual MongoDB URI if hosting on Atlas
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "ClashHunt"
COLLECTION_NAME = "player_timers"

def get_mongo_collection():
    """Initializes and returns the MongoDB collection."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]
    except Exception as e:
        print(f"[MongoDB Error] Could not connect to database: {e}")
        return None

def save_to_history(data_string):
    file_name = "json/request.json"
    table_file = "json/table.json"
    accounts_file = "json/accounts.json"

    # 1. Load reference lookup table mapping data_ids to item_names
    table_lookup = {}
    if os.path.exists(table_file):
        try:
            with open(table_file, "r", encoding="utf-8") as f:
                table_data = json.load(f)
                for item in table_data:
                    table_lookup[int(item["data_id"])] = item
        except Exception as e:
            print(f"[Logger Warning] Could not process table.json lookup index: {e}")

    # 2. Load accounts registry to map player_tags to correct names
    accounts_lookup = {}
    if os.path.exists(accounts_file):
        try:
            with open(accounts_file, "r", encoding="utf-8") as f:
                accounts_data = json.load(f)
                for account in accounts_data:
                    tag = account.get("player_tag")
                    name = account.get("player_name")
                    if tag and name:
                        accounts_lookup[tag] = name
        except Exception as e:
            print(f"[Logger Warning] Could not process accounts.json lookup index: {e}")

    try:
        raw_data = json.loads(data_string)
        
        # 3. Extract top-level metadata & map accurate player name
        player_tag = raw_data.get("tag", "UNKNOWN_TAG")
        player_name = accounts_lookup.get(player_tag, "JAAT")
        
        sync_time = datetime.now(timezone.utc)
        flattened_timers = []

        for category, items in raw_data.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and "timer" in item:
                        data_id = int(item.get("data", 0))
                        seconds_left = int(item["timer"])
                        
                        mapped_info = table_lookup.get(data_id, {})
                        item_name = mapped_info.get("item_name", f"Unknown ID ({data_id})")
                        item_type = mapped_info.get("type", category.capitalize().rstrip('s'))
                        
                        current_lvl = int(item.get("lvl", 0))
                        upgrading_to = str(current_lvl + 1)
                        
                        estimated_finish = sync_time + timedelta(seconds=seconds_left)
                        
                        formatted_item = {
                            "id": f"{player_tag}{item_type}{upgrading_to}{item_name.replace(' ', '')}{seconds_left}",
                            "player_tag": player_tag,
                            "player_name": player_name,
                            "item_name": item_name,
                            "type": item_type,
                            "upgrading_to_level": upgrading_to,
                            "original_seconds_left": str(seconds_left),
                            "sync_timestamp": sync_time.strftime("%Y-%m-%d %H:%M:%S.%f+00"),
                            "estimated_finish_time": estimated_finish.strftime("%Y-%m-%d %H:%M:%S.%f+00"),
                            "typeimageurl": mapped_info.get("typeimageurl"),
                            "imageurl": mapped_info.get("imageurl"),
                            "posturl": mapped_info.get("posturl")
                        }
                        flattened_timers.append(formatted_item)
        
        data_to_save = flattened_timers

    except json.JSONDecodeError:
        print("[Logger Error] Incoming data is not valid JSON string.")
        return

    # -------------------------------------------------------------
    # 📝 LOCAL FILE SAVE LOGIC
    # -------------------------------------------------------------
    if os.path.exists(file_name):
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                history = json.load(f)
                if not isinstance(history, list):
                    history = []
        except json.JSONDecodeError:
            history = []
    else:
        history = []

    cleaned_history = [entry for entry in history if isinstance(entry, dict) and entry.get("player_tag") != player_tag]
    cleaned_history.extend(data_to_save)

    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(cleaned_history, f, indent=4)
    
    print(f"[Success] Updated local JSON file for player: {player_name} ({player_tag})")

    # -------------------------------------------------------------
    # 🍃 MONGODB SAVE LOGIC (Cleans older data & inserts fresh batch)
    # -------------------------------------------------------------
    collection = get_mongo_collection()
    if collection is not None:
        try:
            # 1. Wipe old records for this specific player tag from MongoDB
            collection.delete_many({"player_tag": player_tag})
            
            # 2. Insert the fresh countdown data if any exists
            if data_to_save:
                collection.insert_many(data_to_save)
                print(f"[Success] MongoDB synchronized. Flushed old and inserted {len(data_to_save)} new records.")
            else:
                print("[MongoDB Info] No active timers found to upload.")
        except Exception as e:
            print(f"[MongoDB Error] Failed to complete DB transaction: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        copied_text = sys.argv[1]
        save_to_history(copied_text)


















#         import sys
# import json
# import os
# from datetime import datetime, timedelta, timezone

# def save_to_history(data_string):
#     file_name = "json/request.json"
#     table_file = "json/table.json"
#     accounts_file = "json/accounts.json"

#     # 1. Load reference lookup table mapping data_ids to item_names
#     table_lookup = {}
#     if os.path.exists(table_file):
#         try:
#             with open(table_file, "r", encoding="utf-8") as f:
#                 table_data = json.load(f)
#                 for item in table_data:
#                     table_lookup[int(item["data_id"])] = item
#         except Exception as e:
#             print(f"[Logger Warning] Could not process table.json lookup index: {e}")

#     # 2. Load accounts registry to map player_tags to correct names
#     accounts_lookup = {}
#     if os.path.exists(accounts_file):
#         try:
#             with open(accounts_file, "r", encoding="utf-8") as f:
#                 accounts_data = json.load(f)
#                 for account in accounts_data:
#                     tag = account.get("player_tag")
#                     name = account.get("player_name")
#                     if tag and name:
#                         accounts_lookup[tag] = name
#         except Exception as e:
#             print(f"[Logger Warning] Could not process accounts.json lookup index: {e}")

#     try:
#         raw_data = json.loads(data_string)
        
#         # 3. Extract top-level metadata & map accurate player name
#         player_tag = raw_data.get("tag", "UNKNOWN_TAG")
#         player_name = accounts_lookup.get(player_tag, "JAAT") # Falls back to JAAT only if tag is missing from accounts.json
        
#         sync_time = datetime.now(timezone.utc)
        
#         flattened_timers = []

#         # Loop through categories like buildings, spells, pets, etc.
#         for category, items in raw_data.items():
#             if isinstance(items, list):
#                 for item in items:
#                     if isinstance(item, dict) and "timer" in item:
#                         data_id = int(item.get("data", 0))
#                         seconds_left = int(item["timer"])
                        
#                         mapped_info = table_lookup.get(data_id, {})
#                         item_name = mapped_info.get("item_name", f"Unknown ID ({data_id})")
#                         item_type = mapped_info.get("type", category.capitalize().rstrip('s'))
                        
#                         current_lvl = int(item.get("lvl", 0))
#                         upgrading_to = str(current_lvl + 1)
                        
#                         estimated_finish = sync_time + timedelta(seconds=seconds_left)
                        
#                         # Format into your exact tracking model template
#                         formatted_item = {
#                             "id": f"{player_tag}{item_type}{upgrading_to}{item_name.replace(' ', '')}{seconds_left}",
#                             "player_tag": player_tag,
#                             "player_name": player_name,
#                             "item_name": item_name,
#                             "type": item_type,
#                             "upgrading_to_level": upgrading_to,
#                             "original_seconds_left": str(seconds_left),
#                             "sync_timestamp": sync_time.strftime("%Y-%m-%d %H:%M:%S.%f+00"),
#                             "estimated_finish_time": estimated_finish.strftime("%Y-%m-%d %H:%M:%S.%f+00"),
#                             "typeimageurl": mapped_info.get("typeimageurl"),
#                             "imageurl": mapped_info.get("imageurl"),
#                             "posturl": mapped_info.get("posturl")
#                         }
#                         flattened_timers.append(formatted_item)
        
#         data_to_save = flattened_timers

#     except json.JSONDecodeError:
#         print("[Logger Error] Incoming data is not valid JSON string.")
#         return

#     # 4. Load existing history file safely
#     if os.path.exists(file_name):
#         try:
#             with open(file_name, "r", encoding="utf-8") as f:
#                 history = json.load(f)
#                 if not isinstance(history, list):
#                     history = []
#         except json.JSONDecodeError:
#             history = []
#     else:
#         history = []

#     # -------------------------------------------------------------
#     # 🛠️ TARGETED WIPE LOGIC (Cleans older data for THIS player only)
#     # -------------------------------------------------------------
#     cleaned_history = [
#         entry for entry in history 
#         if isinstance(entry, dict) and entry.get("player_tag") != player_tag
#     ]
    
#     # Append all the fresh countdown records for this specific player tag
#     cleaned_history.extend(data_to_save)
#     # -------------------------------------------------------------

#     # Save tracking file updates cleanly
#     with open(file_name, "w", encoding="utf-8") as f:
#         json.dump(cleaned_history, f, indent=4)
    
#     print(f"[Success] Updated history loop. Flushed old records for player: {player_name} ({player_tag})")

# if __name__ == "__main__":
#     if len(sys.argv) > 1:
#         copied_text = sys.argv[1]
#         save_to_history(copied_text)
