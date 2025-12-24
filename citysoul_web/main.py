import uvicorn
import os
import random
import httpx
import base64
import math
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pymongo import MongoClient
from bson.objectid import ObjectId

app = FastAPI()

# --- CONFIG ---
# PASTE YOUR MONGODB LINK HERE inside the quotes!
MONGO_URI = "mongodb+srv://snepnap:Anand@123@cluster0.oo1itji.mongodb.net/?appName=Cluster0" 

client = MongoClient(MONGO_URI)
db = client.tourbuddy_db  # Name of your database
places_col = db.places
users_col = db.users
reviews_col = db.reviews

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
IMG_DIR = os.path.join(STATIC_DIR, "images")
os.makedirs(IMG_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory="templates")

SESSIONS = {}

# --- UTILS ---
def get_places_data():
    # Convert MongoDB documents to our old dictionary format
    data = {"bilaspur": {"events": ["🎭 Raut Nacha", "🥘 Food Fest"], "places": [], "food": [], "shopping": [], "hotels": []}}
    
    # If DB is empty, add default data
    if places_col.count_documents({}) == 0:
        default_items = [
            {"id": "b1", "name": "Mahamaya Temple", "rating": 4.9, "category": "places", "budget": "Free", "lat": 22.2922, "lon": 82.1670, "desc": "Ancient Shakti Peeth.", "img": "https://placehold.co/600x400/2dd4bf/000000?text=Temple"},
            {"id": "b2", "name": "Kanan Pendari Zoo", "rating": 4.5, "category": "places", "budget": "₹", "lat": 22.1264, "lon": 82.0833, "desc": "Zoological park.", "img": "https://placehold.co/600x400/2dd4bf/000000?text=Zoo"}
        ]
        places_col.insert_many(default_items)
    
    # Fetch all items
    items = list(places_col.find({}, {'_id': 0}))
    for item in items:
        cat = item.get('category', 'places')
        if cat in ["secret_places", "colleges"]: cat = "places"
        if cat in data["bilaspur"]:
            data["bilaspur"][cat].append(item)
    return data

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

# --- MODELS ---
class LoginData(BaseModel):
    username: str
    password: str

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.post("/login")
async def login(data: LoginData):
    if data.username == "admin" and data.password == "password123":
        token = str(random.randint(10000,99999))
        SESSIONS[token] = "admin"
        return JSONResponse(content={"status": "success", "token": token, "role": "admin"})
    
    user = users_col.find_one({"username": data.username})
    if user and user['password'] == data.password:
        token = str(random.randint(10000,99999))
        SESSIONS[token] = data.username
        return JSONResponse(content={"status": "success", "token": token, "role": "user"})
        
    return JSONResponse(content={"status": "error", "message": "Invalid Credentials"})

@app.post("/register")
async def register(data: LoginData):
    if users_col.find_one({"username": data.username}):
        return JSONResponse(content={"status": "error", "message": "Username taken"})
    users_col.insert_one({"username": data.username, "password": data.password})
    return JSONResponse(content={"status": "success", "message": "Account Created"})

@app.get("/api/cities")
async def get_cities():
    return ["bilaspur"] # Simplified for now

@app.get("/admin/api/items/{city}/{category}")
async def get_admin_items(city: str, category: str, token: str):
    if token not in SESSIONS or SESSIONS[token] != "admin": return []
    return list(places_col.find({"category": category}, {'_id': 0}))

# Using Form for these endpoints for compatibility
from fastapi import Form 

@app.post("/discover_places")
async def discover_places(city: str = Form(...), type: str = Form("places"), user_lat: float = Form(0), user_lon: float = Form(0)):
    if type in ["secret_places", "colleges"]: type = "places"
    
    # Fetch from MongoDB
    items = list(places_col.find({"category": type}, {'_id': 0}))
    
    for item in items:
        # Calculate rating
        revs = list(reviews_col.find({"place_id": item['id']}))
        item['rating'] = round(sum(int(r['rating']) for r in revs)/len(revs), 1) if revs else 0
        item['review_count'] = len(revs)
        
        if user_lat != 0 and user_lon != 0:
            item['distance'] = calculate_distance(user_lat, user_lon, item.get('lat', 0), item.get('lon', 0))
        else: item['distance'] = "N/A"

    return JSONResponse(content={"items": items, "city": city.title()})

@app.post("/add_place")
async def add_place(city: str = Form(...), category_type: str = Form(...), name: str = Form(...), desc: str = Form(...), img_url: str = Form(...), budget: str = Form(...), lat: float = Form(...), lon: float = Form(...), user: str = Form("Guest")):
    if category_type in ["secret_places", "colleges"]: category_type = "places"
    
    final_img = "https://placehold.co/600x400/1e293b/ffffff?text=TourBuddy"
    if img_url and "base64" in img_url:
        try:
            fname = f"img_{random.randint(1000,9999)}.jpg"
            # NOTE: For production, you should upload to a cloud service (Cloudinary/S3). 
            # Saving to disk on Render Free tier will still disappear, but the DATA (name, lat, lon) will stay in Mongo.
            # For now, we save metadata to Mongo.
            final_img = img_url # Storing base64 directly or external URL is safer for persistence on free tier without S3
        except: pass

    new_item = {
        "id": f"usr{random.randint(1000,9999)}", 
        "name": name, 
        "category": category_type, 
        "budget": budget, 
        "lat": lat, 
        "lon": lon, 
        "desc": desc, 
        "img": final_img
    }
    places_col.insert_one(new_item)
    return JSONResponse(content={"status": "success", "message": "Added to Cloud DB!"})

@app.post("/admin_delete")
async def admin_delete(city: str = Form(...), category: str = Form(...), id: str = Form(...), token: str = Form(...)):
    if token not in SESSIONS or SESSIONS[token] != "admin": return JSONResponse(content={"status": "error", "message": "Unauthorized"})
    places_col.delete_one({"id": id})
    return JSONResponse(content={"status": "success", "message": "Deleted"})

@app.post("/admin_update_image")
async def admin_update_image(city: str = Form(...), category: str = Form(...), id: str = Form(...), img_url: str = Form(...), token: str = Form(...)):
    if token not in SESSIONS or SESSIONS[token] != "admin": return JSONResponse(content={"status": "error", "message": "Unauthorized"})
    places_col.update_one({"id": id}, {"$set": {"img": img_url}})
    return JSONResponse(content={"status": "success", "message": "Image Updated!"})

@app.post("/submit_review")
async def submit_review(place_id: str = Form(...), user_name: str = Form(...), rating: int = Form(...), review_text: str = Form(...)):
    reviews_col.insert_one({
        "place_id": place_id,
        "user": user_name, 
        "rating": rating, 
        "text": review_text, 
        "date": datetime.now().strftime("%Y-%m-%d")
    })
    return JSONResponse(content={"status": "success"})

@app.post("/get_reviews")
async def get_reviews(place_id: str = Form(...)):
    revs = list(reviews_col.find({"place_id": place_id}, {'_id': 0}))
    avg = round(sum(int(r['rating']) for r in revs)/len(revs), 1) if revs else 0
    return JSONResponse(content={"reviews": revs, "average": avg, "count": len(revs)})

# Standard Utilities
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
    data = get_places_data()
    key = dest_city.lower().strip()
    city_data = data.get(key, {})
    all_spots = city_data.get("places", []) + city_data.get("food", [])
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

@app.post("/ask_ai")
async def ask_ai(query: str = Form(...), city: str = Form(...)):
    return JSONResponse(content={"response": f"TourBuddy suggests exploring {city}!"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)