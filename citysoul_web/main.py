import uvicorn
import json
import os
import random
import httpx
import shutil
import base64
import math
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "database.json")
USERS_FILE = os.path.join(BASE_DIR, "users.json")
REVIEWS_FILE = os.path.join(BASE_DIR, "reviews.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")
IMG_DIR = os.path.join(STATIC_DIR, "images")

os.makedirs(IMG_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory="templates")

# --- UTILS ---
def load_json(filename):
    if not os.path.exists(filename): return {}
    try: 
        with open(filename, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

def calculate_distance(lat1, lon1, lat2, lon2):
    if not lat1 or not lat2: return "N/A"
    try:
        R = 6371 
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return f"{round(R * c, 1)} km"
    except: return "N/A"

# --- INIT DATA ---
CITY_DATA = load_json(DB_FILE)
if not CITY_DATA:
    CITY_DATA = {
        "bilaspur": {
            "events": ["🎭 Raut Nacha", "🥘 Food Fest"],
            "places": [
                {"id": "b1", "name": "Mahamaya Temple", "rating": 4.9, "category": "Spiritual", "budget": "Free", "lat": 22.2922, "lon": 82.1670, "desc": "Ancient Shakti Peeth.", "img": "https://placehold.co/600x400/2dd4bf/000000?text=Temple"},
                {"id": "b2", "name": "Kanan Pendari Zoo", "rating": 4.5, "category": "Wildlife", "budget": "₹", "lat": 22.1264, "lon": 82.0833, "desc": "Zoological park.", "img": "https://placehold.co/600x400/2dd4bf/000000?text=Zoo"}
            ],
            "food": [], "shopping": [], "hotels": []
        }
    }
    save_json(DB_FILE, CITY_DATA)

USER_DB = load_json(USERS_FILE)
REVIEWS_DB = load_json(REVIEWS_FILE)
SESSIONS = {}

# --- MODELS (NEW JSON LOGIN) ---
class LoginData(BaseModel):
    username: str
    password: str

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/login")
async def login(data: LoginData):
    # 1. Admin Check
    if data.username == "admin" and data.password == "password123":
        token = str(random.randint(10000,99999))
        SESSIONS[token] = "admin"
        return JSONResponse(content={"status": "success", "token": token, "role": "admin"})
    
    # 2. User Check
    global USER_DB; USER_DB = load_json(USERS_FILE)
    u = USER_DB.get(data.username)
    stored_pass = u if isinstance(u, str) else u.get("password") if u else None
    
    if stored_pass == data.password:
        token = str(random.randint(10000,99999))
        SESSIONS[token] = data.username
        return JSONResponse(content={"status": "success", "token": token, "role": "user"})
        
    return JSONResponse(content={"status": "error", "message": "Invalid Credentials"})

@app.post("/register")
async def register(data: LoginData):
    global USER_DB; USER_DB = load_json(USERS_FILE)
    if data.username in USER_DB: return JSONResponse(content={"status": "error", "message": "Username taken"})
    USER_DB[data.username] = {"password": data.password, "xp": 0}
    save_json(USERS_FILE, USER_DB)
    return JSONResponse(content={"status": "success", "message": "Account Created"})

# IMPORTANT: The following endpoints still use Form data for file uploads (Requires python-multipart eventually)
# But Login is now fixed regardless.

from fastapi import Form 

@app.post("/admin_delete")
async def admin_delete(city: str = Form(...), category: str = Form(...), id: str = Form(...), token: str = Form(...)):
    if token not in SESSIONS or SESSIONS[token] != "admin": return JSONResponse(content={"status": "error", "message": "Unauthorized"})
    global CITY_DATA; key = city.lower().strip()
    if category in ["secret_places", "colleges"]: category = "places"
    CITY_DATA[key][category] = [i for i in CITY_DATA[key][category] if i['id'] != id]
    save_json(DB_FILE, CITY_DATA)
    return JSONResponse(content={"status": "success", "message": "Deleted"})

@app.post("/admin_update_image")
async def admin_update_image(city: str = Form(...), category: str = Form(...), id: str = Form(...), img_url: str = Form(...), token: str = Form(...)):
    if token not in SESSIONS or SESSIONS[token] != "admin": return JSONResponse(content={"status": "error", "message": "Unauthorized"})
    global CITY_DATA; key = city.lower().strip()
    if category in ["secret_places", "colleges"]: category = "places"
    
    target_list = CITY_DATA[key].get(category, [])
    for item in target_list:
        if item['id'] == id:
            if img_url and "base64" in img_url:
                try:
                    ext = "png" if "png" in img_url.split(",", 1)[0] else "jpg"
                    fname = f"update_{id}_{random.randint(1000,9999)}.{ext}"
                    with open(os.path.join(IMG_DIR, fname), "wb") as f: f.write(base64.b64decode(img_url.split(",", 1)[1]))
                    item['img'] = f"/static/images/{fname}"
                    save_json(DB_FILE, CITY_DATA)
                    return JSONResponse(content={"status": "success", "message": "Image Updated!"})
                except: return JSONResponse(content={"status": "error", "message": "Save failed"})
    return JSONResponse(content={"status": "error", "message": "Item not found"})

@app.post("/get_weather")
async def get_weather(city: str = Form(...)):
    try:
        async with httpx.AsyncClient() as client:
            geo = await client.get(f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1", headers={'User-Agent': 'TourBuddy'}, timeout=2.0)
            data = geo.json()
            if not data: return JSONResponse(content={"status": "error"})
            w = await client.get(f"https://api.open-meteo.com/v1/forecast?latitude={data[0]['lat']}&longitude={data[0]['lon']}&current_weather=true", timeout=2.0)
            return JSONResponse(content={"status": "success", "temp": w.json()['current_weather']['temperature']})
    except: return JSONResponse(content={"status": "error"})

@app.post("/geocode")
async def geocode(address: str = Form(...)):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1", headers={'User-Agent': 'TourBuddy'}, timeout=3.0)
            data = res.json()
            if data: return JSONResponse(content={"status": "success", "lat": float(data[0]['lat']), "lon": float(data[0]['lon'])})
    except: pass
    return JSONResponse(content={"status": "error"})

@app.post("/plan_route")
async def plan_route(user_lat: float = Form(...), user_lon: float = Form(...), dest_city: str = Form(...)):
    global CITY_DATA; CITY_DATA = load_json(DB_FILE)
    key = dest_city.lower().strip()
    data = CITY_DATA.get(key, {})
    all_spots = data.get("places", []) + data.get("food", [])
    stops = random.sample(all_spots, min(3, len(all_spots))) if all_spots else []
    dest_lat, dest_lon = (stops[-1]['lat'], stops[-1]['lon']) if stops else (0,0)
    if dest_lat == 0:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"https://nominatim.openstreetmap.org/search?q={dest_city}&format=json&limit=1", headers={'User-Agent': 'TourBuddy'}, timeout=2.0)
                geo = res.json()
                if geo: dest_lat, dest_lon = float(geo[0]['lat']), float(geo[0]['lon'])
        except: pass
    route = [{"step": 0, "name": "Start", "lat": user_lat, "lon": user_lon}]
    for i, s in enumerate(stops): route.append({"step": i+1, "name": s['name'], "lat": s.get('lat', dest_lat), "lon": s.get('lon', dest_lon)})
    return JSONResponse(content={"status": "success", "route": route})

@app.post("/discover_places")
async def discover_places(city: str = Form(...), type: str = Form("places"), user_lat: float = Form(0), user_lon: float = Form(0)):
    global CITY_DATA, REVIEWS_DB
    CITY_DATA = load_json(DB_FILE)
    REVIEWS_DB = load_json(REVIEWS_FILE)
    key = city.lower().strip()
    data = CITY_DATA.get(key, {})
    if type in ["secret_places", "colleges"]: type = "places"
    items = data.get(type, []) 
    for item in items:
        revs = REVIEWS_DB.get(item['id'], [])
        item['rating'] = round(sum(int(r['rating']) for r in revs)/len(revs), 1) if revs else 0
        item['review_count'] = len(revs)
        if user_lat != 0 and user_lon != 0:
            item['distance'] = calculate_distance(user_lat, user_lon, item.get('lat', 0), item.get('lon', 0))
        else: item['distance'] = "N/A"
    return JSONResponse(content={"items": items, "city": city.title()})

@app.post("/add_place")
async def add_place(city: str = Form(...), category_type: str = Form(...), name: str = Form(...), desc: str = Form(...), img_url: str = Form(...), budget: str = Form(...), lat: float = Form(...), lon: float = Form(...), user: str = Form("Guest")):
    global CITY_DATA; key = city.lower().strip()
    if key not in CITY_DATA: CITY_DATA[key] = {"places": [], "hotels": [], "food": [], "shopping": [], "events": []}
    if category_type in ["secret_places", "colleges"]: category_type = "places"
    if category_type not in CITY_DATA[key]: CITY_DATA[key][category_type] = []
    final_img = "https://placehold.co/600x400/1e293b/ffffff?text=TourBuddy"
    if img_url and "base64" in img_url:
        try:
            fname = f"{key}_{random.randint(1000,9999)}.jpg"
            with open(os.path.join(IMG_DIR, fname), "wb") as f: f.write(base64.b64decode(img_url.split(",", 1)[1]))
            final_img = f"/static/images/{fname}"
        except: pass
    new_item = {"id": f"usr{random.randint(1000,9999)}", "name": name, "rating": 0.0, "category": "User Added", "budget": budget, "lat": lat, "lon": lon, "desc": desc, "img": final_img}
    CITY_DATA[key][category_type].insert(0, new_item)
    save_json(DB_FILE, CITY_DATA)
    return JSONResponse(content={"status": "success", "message": "Added!"})

@app.post("/submit_review")
async def submit_review(place_id: str = Form(...), user_name: str = Form(...), rating: int = Form(...), review_text: str = Form(...)):
    global REVIEWS_DB; REVIEWS_DB.setdefault(place_id, [])
    REVIEWS_DB[place_id].insert(0, {"user": user_name, "rating": rating, "text": review_text, "date": datetime.now().strftime("%Y-%m-%d")})
    save_json(REVIEWS_FILE, REVIEWS_DB)
    return JSONResponse(content={"status": "success"})

@app.post("/get_reviews")
async def get_reviews(place_id: str = Form(...)):
    global REVIEWS_DB; REVIEWS_DB = load_json(REVIEWS_FILE)
    revs = REVIEWS_DB.get(place_id, [])
    avg = round(sum(int(r['rating']) for r in revs)/len(revs), 1) if revs else 0
    return JSONResponse(content={"reviews": revs, "average": avg, "count": len(revs)})

@app.post("/ask_ai")
async def ask_ai(query: str = Form(...), city: str = Form(...)):
    return JSONResponse(content={"response": f"TourBuddy suggests exploring {city}!"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)