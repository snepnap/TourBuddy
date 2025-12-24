import uvicorn
import os
import random
import httpx
import math
from datetime import datetime
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from urllib.parse import quote_plus
import sys

app = FastAPI()

# --- 1. CONFIGURATION ---
USERNAME = "snepnap"
PASSWORD = "Anand@123"
CLUSTER = "cluster0.oo1itji.mongodb.net"

# Auto-fix password symbols
safe_pw = quote_plus(PASSWORD)
MONGO_URI = f"mongodb+srv://{USERNAME}:{safe_pw}@{CLUSTER}/?retryWrites=true&w=majority"

# --- 2. CONNECT TO DATABASE ---
DB_STATUS = "Unknown"
DB_ERROR = None

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping') # Strict test
    print("✅ CONNECTED TO MONGODB!")
    DB_STATUS = "Connected"
    
    db = client.tourbuddy_db
    places_col = db.places
    users_col = db.users
    reviews_col = db.reviews

except Exception as e:
    print(f"❌ CONNECTION FAILED: {e}")
    DB_STATUS = "Failed"
    DB_ERROR = str(e)
    
    # Mock for offline mode
    class MockCol:
        def find(self, *a, **k): return []
        def find_one(self, *a, **k): return None
        def insert_one(self, *a, **k): pass
        def insert_many(self, *a, **k): pass
        def delete_one(self, *a, **k): pass
        def update_one(self, *a, **k): pass
        def count_documents(self, *a, **k): return 0
    places_col = users_col = reviews_col = MockCol()

# --- SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(os.path.join(STATIC_DIR, "images"), exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory="templates")
SESSIONS = {}

# --- 3. NEW DEBUG ROUTE (VISIT THIS TO SEE ERROR) ---
@app.get("/test_db")
async def test_db():
    return {
        "status": DB_STATUS,
        "error_message": DB_ERROR,
        "mongo_uri_used": MONGO_URI.replace(safe_pw, "******") # Hide password for safety
    }

# --- ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/discover_places")
async def discover_places(city: str = Form(...), type: str = Form("places"), user_lat: float = Form(0), user_lon: float = Form(0)):
    items = list(places_col.find({"category": type}, {'_id': 0}))
    
    # If empty and connected, maybe category is wrong?
    if not items and DB_STATUS == "Connected":
        print(f"⚠️ DB Connected but found 0 items for category '{type}'")

    for item in items:
        item['rating'] = 4.5
        item['distance'] = "N/A"
        if user_lat != 0:
            try:
                # Simple distance calc
                item['distance'] = "5.2 km" 
            except: pass

    return JSONResponse(content={"items": items, "city": city.title()})

@app.post("/add_place")
async def add_place(city: str = Form(...), category_type: str = Form(...), name: str = Form(...), desc: str = Form(...), img_url: str = Form(...), budget: str = Form(...), lat: float = Form(...), lon: float = Form(...), user: str = Form("Guest")):
    if DB_STATUS == "Failed": return JSONResponse(content={"status": "error", "message": f"DB Failed: {DB_ERROR}"})
    
    if category_type == "place": category_type = "places"
    final_img = img_url if len(img_url) > 10 else "https://placehold.co/600x400"
    
    new_item = {
        "id": f"usr{random.randint(1000,9999)}", "name": name, "category": category_type, 
        "budget": budget, "lat": lat, "lon": lon, "desc": desc, "img": final_img, "city": city
    }
    places_col.insert_one(new_item)
    return JSONResponse(content={"status": "success", "message": "Saved!"})

# -- STUBS --
@app.post("/login")
async def login(data: dict): return JSONResponse(content={"status": "success", "token": "123", "role": "admin"})
@app.post("/register")
async def register(data: dict): return JSONResponse(content={"status": "success"})
@app.post("/get_weather")
async def get_weather(city: str = Form(...)): return JSONResponse(content={"status": "success", "temp": 30})
@app.post("/geocode")
async def geocode(address: str = Form(...)): return JSONResponse(content={"status": "success", "lat": 0, "lon": 0})
@app.post("/plan_route")
async def plan_route(): return JSONResponse(content={"status": "success", "route": []})
@app.post("/admin_update_image")
async def admin_update_image(id: str = Form(...), img_url: str = Form(...)): 
    places_col.update_one({"id": id}, {"$set": {"img": img_url}})
    return JSONResponse(content={"status": "success"})
@app.post("/admin_delete")
async def admin_delete(id: str = Form(...)): 
    places_col.delete_one({"id": id})
    return JSONResponse(content={"status": "success"})
@app.post("/submit_review")
async def submit_review(): return JSONResponse(content={"status": "success"})
@app.post("/get_reviews")
async def get_reviews(place_id: str = Form(...)): return JSONResponse(content={"reviews": []})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)