import uvicorn
import os
import random
import httpx
import math
import certifi
from datetime import datetime
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient

app = FastAPI()

# --- 1. SECURE CONNECTION SETUP ---
# We no longer type the password here. We get it from the Server's Safe.
MONGO_URI = os.getenv("MONGO_URL")

# Fallback check (Just in case you forgot Step 1)
if not MONGO_URI:
    print("❌ ERROR: MONGO_URL not found! Did you add it to Render Environment Variables?")

# --- 2. CONNECT TO DATABASE ---
try:
    # Use certifi for SSL safety
    ca = certifi.where()
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tlsCAFile=ca)
    
    # Test connection
    client.admin.command('ping')
    print("✅ CONNECTED TO MONGODB SUCCESSFULLY!")
    
    db = client.tourbuddy_db
    places_col = db.places
    users_col = db.users
    reviews_col = db.reviews
    IS_OFFLINE = False

    # Auto-Create Admin (Secure)
    # Note: We use a default password only if creating a NEW admin.
    if not users_col.find_one({"username": "admin"}):
        print(f"👤 Admin user missing. Creating default admin...")
        users_col.insert_one({
            "username": "admin",
            "password": "Admin@12345", # You can change this later in DB
            "role": "admin"
        })

except Exception as e:
    print(f"❌ DATABASE ERROR: {e}")
    print("⚠️ STARTING IN OFFLINE MODE")
    IS_OFFLINE = True
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
IMG_DIR = os.path.join(STATIC_DIR, "images")
os.makedirs(IMG_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory="templates")
SESSIONS = {}

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.post("/login")
async def login(data: dict):
    if IS_OFFLINE: return JSONResponse(content={"status": "error", "message": "Database Offline"})

    user = users_col.find_one({"username": data.get('username')})
    if user and user['password'] == data.get('password'):
        token = str(random.randint(10000,99999))
        SESSIONS[token] = user['username']
        role = user.get("role", "user")
        return JSONResponse(content={"status": "success", "token": token, "role": role})
        
    return JSONResponse(content={"status": "error", "message": "Invalid Credentials"})

@app.post("/register")
async def register(data: dict):
    if IS_OFFLINE: return JSONResponse(content={"status": "error", "message": "Database Offline"})
    if users_col.find_one({"username": data.get('username')}):
        return JSONResponse(content={"status": "error", "message": "Username taken"})
    users_col.insert_one({"username": data.get('username'), "password": data.get('password'), "role": "user"})
    return JSONResponse(content={"status": "success", "message": "Account Created"})

@app.post("/discover_places")
async def discover_places(city: str = Form(...), type: str = Form("places"), user_lat: float = Form(0), user_lon: float = Form(0)):
    if type in ["secret_places", "colleges"]: type = "places"
    
    target_city = city.lower().strip()
    items = list(places_col.find({
        "category": type,
        "city": {"$regex": f"^{target_city}$", "$options": "i"}
    }, {'_id': 0}))
    
    for item in items:
        revs = list(reviews_col.find({"place_id": item['id']}))
        item['rating'] = round(sum(int(r['rating']) for r in revs)/len(revs), 1) if revs else 0
        
        if user_lat != 0 and user_lon != 0:
            try:
                R = 6371
                lat1, lon1 = math.radians(user_lat), math.radians(user_lon)
                lat2, lon2 = math.radians(item.get('lat',0)), math.radians(item.get('lon',0))
                dlon = lon2 - lon1
                dlat = lat2 - lat1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                c = 2 * math.asin(math.sqrt(a))
                item['distance'] = f"{round(R * c, 1)} km"
            except: item['distance'] = "N/A"
        else: item['distance'] = "N/A"

    return JSONResponse(content={"items": items, "city": city.title()})

@app.post("/add_place")
async def add_place(city: str = Form(...), category_type: str = Form(...), name: str = Form(...), desc: str = Form(...), img_url: str = Form(...), budget: str = Form(...), lat: float = Form(...), lon: float = Form(...), user: str = Form("Guest")):
    if IS_OFFLINE: return JSONResponse(content={"status": "error", "message": "DB Error - Check Logs"})
    if category_type == "place": category_type = "places"
    
    final_img = "https://placehold.co/600x400/1e293b/ffffff?text=TourBuddy"
    if img_url and len(img_url) > 10: final_img = img_url

    new_item = {"id": f"usr{random.randint(1000,9999)}", "name": name, "category": category_type, "budget": budget, "lat": lat, "lon": lon, "desc": desc, "img": final_img, "city": city}
    places_col.insert_one(new_item)
    return JSONResponse(content={"status": "success", "message": "Added to Cloud DB!"})

@app.post("/admin_delete")
async def admin_delete(city: str = Form(...), category: str = Form(...), id: str = Form(...), token: str = Form(...)):
    if token not in SESSIONS: return JSONResponse(content={"status": "error", "message": "Login required"})
    places_col.delete_one({"id": id})
    return JSONResponse(content={"status": "success", "message": "Deleted"})

@app.post("/admin_update_image")
async def admin_update_image(city: str = Form(...), category: str = Form(...), id: str = Form(...), img_url: str = Form(...), token: str = Form(...)):
    if token not in SESSIONS: return JSONResponse(content={"status": "error", "message": "Unauthorized"})
    places_col.update_one({"id": id}, {"$set": {"img": img_url}})
    return JSONResponse(content={"status": "success", "message": "Image Updated!"})

@app.post("/submit_review")
async def submit_review(place_id: str = Form(...), user_name: str = Form(...), rating: int = Form(...), review_text: str = Form(...)):
    if IS_OFFLINE: return JSONResponse(content={"status": "error"})
    reviews_col.insert_one({"place_id": place_id, "user": user_name, "rating": rating, "text": review_text, "date": datetime.now().strftime("%Y-%m-%d")})
    return JSONResponse(content={"status": "success"})

@app.post("/get_reviews")
async def get_reviews(place_id: str = Form(...)):
    revs = list(reviews_col.find({"place_id": place_id}, {'_id': 0}))
    return JSONResponse(content={"reviews": revs})

# --- UTILS (Weather/Route) ---
@app.post("/get_weather")
async def get_weather(city: str = Form(...)):
    try:
        async with httpx.AsyncClient() as client:
            geo = await client.get(f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1", headers={'User-Agent': 'TourBuddy'}, timeout=4.0)
            data = geo.json()
            if not data: return JSONResponse(content={"status": "error"})
            w = await client.get(f"https://api.open-meteo.com/v1/forecast?latitude={data[0]['lat']}&longitude={data[0]['lon']}&current_weather=true", timeout=4.0)
            return JSONResponse(content={"status": "success", "temp": w.json()['current_weather']['temperature']})
    except: return JSONResponse(content={"status": "error"})

@app.post("/geocode")
async def geocode(address: str = Form(...)):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1", headers={'User-Agent': 'TourBuddy'}, timeout=4.0)
            data = res.json()
            if data: return JSONResponse(content={"status": "success", "lat": float(data[0]['lat']), "lon": float(data[0]['lon'])})
    except: pass
    return JSONResponse(content={"status": "error"})

@app.post("/plan_route")
async def plan_route(user_lat: float = Form(...), user_lon: float = Form(...), dest_city: str = Form(...)):
    return JSONResponse(content={"status": "success", "route": [{"step":1, "name":"Start", "lat":user_lat, "lon":user_lon}, {"step":2, "name":dest_city, "lat":user_lat+0.01, "lon":user_lon+0.01}]})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)