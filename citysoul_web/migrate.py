import json
import random
from pymongo import MongoClient
from urllib.parse import quote_plus

# --- CONFIGURATION (Already Filled For You) ---
USERNAME = "snepnap"
PASSWORD = "Anand@123"
CLUSTER = "cluster0.oo1itji.mongodb.net"

# Auto-fix the special '@' symbol in your password
safe_user = quote_plus(USERNAME)
safe_pass = quote_plus(PASSWORD)

# Create the correct link
MONGO_URI = f"mongodb+srv://{safe_user}:{safe_pass}@{CLUSTER}/?retryWrites=true&w=majority&appName=Cluster0"

try:
    print(f"🔌 Connecting to Cloud Database...")
    
    # 1. Connect
    client = MongoClient(MONGO_URI)
    db = client.tourbuddy_db
    places_col = db.places
    
    # Test connection
    client.admin.command('ping')
    print("✅ Connected to MongoDB successfully!")

    # 2. Load Local Data
    try:
        with open("database.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        print("📂 Loaded database.json...")
    except FileNotFoundError:
        print("❌ ERROR: Could not find 'database.json' in this folder. Make sure it exists!")
        exit()

    # 3. Upload Data
    count = 0
    # Loop through cities (e.g. "bilaspur")
    for city, categories in data.items():
        if not isinstance(categories, dict): continue
        
        # Loop through categories (places, food, etc.)
        for category, items in categories.items():
            if category == "events": continue 
            
            for item in items:
                # Create clean item for Cloud
                new_item = {
                    "id": item.get("id", f"mig_{random.randint(1000,9999)}"),
                    "name": item.get("name"),
                    "category": category,
                    "desc": item.get("desc", "No description"),
                    "img": item.get("img", ""),
                    "lat": item.get("lat", 0),
                    "lon": item.get("lon", 0),
                    "budget": item.get("budget", "N/A"),
                    "city": city 
                }
                
                # Check if it already exists to prevent double-copying
                if not places_col.find_one({"name": new_item["name"]}):
                    places_col.insert_one(new_item)
                    count += 1
                    print(f"   -> Uploaded: {new_item['name']}")
                else:
                    print(f"   -> Skipped (Already exists): {new_item['name']}")

    print(f"\n🎉 SUCCESS! Uploaded {count} items to the cloud.")

except Exception as e:
    print(f"\n❌ ERROR: {e}")