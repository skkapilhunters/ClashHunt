import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase using JSON string from environment variables
firebase_creds_json = os.getenv("FIREBASE_CREDENTIALS")

if firebase_creds_json:
    try:
        # Parse the JSON string from .env
        cred_dict = json.loads(firebase_creds_json)
        
        # Initialize Firebase if not already initialized
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            
        db = firestore.client()
        print("🔥 [Firebase] Successfully initialized using environment variables!")
    except Exception as e:
        print(f"❌ [Firebase Init Error] Failed to parse credentials: {e}")
        db = None
else:
    print("⚠️ [Firebase Warning] FIREBASE_CREDENTIALS environment variable is missing!")
    db = None


async def export_war_to_firebase(clan_tag: str, guild_id: int, conflict_data: dict) -> bool:
    """
    Exports ended war documents directly to Firebase Firestore.
    """
    if not db:
        print("❌ [Firebase Error] Cannot migrate: Database client is not initialized.")
        return False

    try:
        clean_tag = clan_tag.replace("#", "")
        prep_start = conflict_data.get("war_metadata", {}).get("prep_day_start", "unknown_date")
        
        # Create a unique, clean document ID (e.g. JPPC80RR_2026-07-28_16-01-11)
        doc_id = f"{clean_tag}_{prep_start.replace(' ', '_').replace(':', '-')}"

        doc_ref = db.collection("ended_wars").document(doc_id)
        
        payload = {
            "clan_tag": clan_tag,
            "guild_id": guild_id,
            "migrated_at": firestore.SERVER_TIMESTAMP,
            "conflict_data": conflict_data
        }

        doc_ref.set(payload, merge=True)
        print(f"🔥 [Firebase] Successfully migrated ended war data for document ID: {doc_id}")
        return True

    except Exception as e:
        print(f"❌ [Firebase Migration Error] {e}")
        return False
