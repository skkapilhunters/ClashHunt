import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# Global Firestore client variable
db = None

def init_firebase():
    """Initializes Firebase Admin SDK using environment variables."""
    global db
    if firebase_admin._apps:
        db = firestore.client()
        return

    firebase_creds_json = os.getenv("FIREBASE_CREDENTIALS")

    if not firebase_creds_json:
        print("⚠️ [Firebase Warning] FIREBASE_CREDENTIALS is missing from .env/secrets!")
        return

    try:
        # Parse the JSON string from environment variables
        cred_dict = json.loads(firebase_creds_json)
        
        # Handle formatted newlines in private key if passed literally
        if "private_key" in cred_dict:
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")

        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("🔥 [Firebase] Successfully initialized Firestore client via ENV secrets!")
    except Exception as e:
        print(f"❌ [Firebase Init Error] Failed to initialize Firebase: {e}")

# Call initialization on module import
init_firebase()


async def export_war_to_firebase(clan_tag: str, guild_id: int, conflict_data: dict) -> bool:
    """
    Archives ended war documents directly to Firebase Firestore.
    Collection: 'ended_wars'
    Document ID Format: CLANTAG_YYYY-MM-DD_HH-MM-SS
    """
    global db
    if not db:
        # Retry initialization in case env variables loaded late
        init_firebase()
        if not db:
            print("❌ [Firebase Error] Skipping migration: Firestore client not initialized.")
            return False

    try:
        # Sanitize clan tag for document key (remove '#')
        clean_tag = clan_tag.replace("#", "")
        prep_start = conflict_data.get("war_metadata", {}).get("prep_day_start", "unknown_date")
        
        # Create a clean, unique ID (e.g., JPPC80RR_2026-07-28_16-01-11)
        doc_id = f"{clean_tag}_{prep_start.replace(' ', '_').replace(':', '-')}"

        doc_ref = db.collection("ended_wars").document(doc_id)
        
        payload = {
            "clan_tag": clan_tag,
            "guild_id": guild_id,
            "migrated_at": firestore.SERVER_TIMESTAMP,
            "conflict_data": conflict_data
        }

        # Merge ensures existing documents update smoothly without deleting fields
        doc_ref.set(payload, merge=True)
        print(f"🔥 [Firebase] Successfully migrated 'War Ended' data for doc: {doc_id}")
        return True

    except Exception as e:
        print(f"❌ [Firebase Migration Error] {e}")
        return False
