import uvicorn
import os
import random
import httpx
import math
import certifi
import cloudinary
import cloudinary.uploader
from datetime import datetime
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient

app = FastAPI()

# --- 1. CLOUDINARY CONFIGURATION ---
cloudinary.config( 
  cloud_name = "dnifw24ax", 
  api_key = "383823447216573", 
  api_secret = "_k1V1aY0mAJeSkHyfPLIDYyIvRc" 
)

# --- 2. SECURE DATABASE CONNECTION ---
MONGO_URI = os.getenv("MONGO_URL")

if not MONGO_URI:
    print("❌ ERROR: MONGO_URL not found! Did you add it to Render Environment Variables?")

try:
    ca = certifi.where()
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tlsCAFile=ca)
    client.admin.command('ping')
    print("✅ CONNECTED TO MONGODB SUCCESSFULLY!")
    
    db = client.tourbuddy_db
    places_col = db.places
    users_col = db.users
    reviews_col = db.reviews
    IS_OFFLINE = False

    if not users_col.find_one({"username": "admin"}):
        print(f"👤 Creating default admin...")
        users_col.insert_one({"username": "admin", "password": "Admin@12345", "role": "admin"})

except Exception as e:
    print(f"❌ DATABASE ERROR: {e}")
    IS_OFFLINE = True
    places_col = users_col = reviews_col = None

# --- SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
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
        return JSONResponse(content={"status": "success", "token": token, "role": user.get("role", "user")})
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
    items = list(places_col.find({"category": type, "city": {"$regex": f"^{target_city}$", "$options": "i"}}, {'_id': 0}))
    
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
async def add_place(
    city: str = Form(...), 
    category_type: str = Form(...), 
    name: str = Form(...), 
    desc: str = Form(...), 
    budget: str = Form(...), 
    file: UploadFile = File(None), 
    lat: str = Form("0"),
    lon: str = Form("0"), 
    user: str = Form("Guest")
):
    if IS_OFFLINE: return JSONResponse(content={"status": "error", "message": "DB Error"})
    if category_type == "place": category_type = "places"
    
    final_img = "https://placehold.co/600x400/1e293b/ffffff?text=TourBuddy"
    
    if file:
        print(f"📸 Uploading image for {name}...")
        try:
            upload_result = cloudinary.uploader.upload(file.file)
            final_img = upload_result.get("url")
            print(f"✅ Image Uploaded: {final_img}")
        except Exception as e:
            print(f"❌ Upload Failed: {e}")

    try: final_lat, final_lon = float(lat), float(lon)
    except: final_lat, final_lon = 0.0, 0.0

    if final_lat == 0 or final_lon == 0:
        print(f"🌍 Auto-locating: {name}...")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://nominatim.openstreetmap.org/search?q={name}, {city}&format=json&limit=1", headers={'User-Agent': 'TourBuddy'})
                data = resp.json()
                if data:
                    final_lat, final_lon = float(data[0]['lat']), float(data[0]['lon'])
                else:
                    r2 = await client.get(f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1", headers={'User-Agent': 'TourBuddy'})
                    d2 = r2.json()
                    if d2: final_lat, final_lon = float(d2[0]['lat']), float(d2[0]['lon'])
        except: pass

    new_item = {
        "id": f"usr{random.randint(1000,9999)}", 
        "name": name, "category": category_type, "budget": budget, 
        "lat": final_lat, "lon": final_lon, "desc": desc, 
        "img": final_img, "city": city, "user": user
    }
    places_col.insert_one(new_item)
    return JSONResponse(content={"status": "success", "message": "Added with Image & Auto-Location!"})

@app.post("/get_user_profile")
async def get_user_profile(username: str = Form(...)):
    if IS_OFFLINE: return JSONResponse(content={"status": "error", "places": [], "reviews": []})
    my_places = list(places_col.find({"user": username}, {'_id': 0}))
    my_reviews = list(reviews_col.find({"user": username}, {'_id': 0}))
    return JSONResponse(content={"status": "success", "places": my_places, "reviews": my_reviews})

@app.post("/admin_delete")
async def admin_delete(id: str = Form(...), token: str = Form(...)):
    if token not in SESSIONS: return JSONResponse(content={"status": "error", "message": "Login required"})
    places_col.delete_one({"id": id})
    return JSONResponse(content={"status": "success", "message": "Deleted"})

@app.post("/admin_update_image")
async def admin_update_image(id: str = Form(...), img_url: str = Form(...), token: str = Form(...)):
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

@app.post("/get_weather")
async def get_weather(city: str = Form(...)):
    try:
        async with httpx.AsyncClient() as client:
            geo = await client.get(f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1", headers={'User-Agent': 'TourBuddy'}, timeout=4.0)
            data = geo.json()
            if data:
                w = await client.get(f"https://api.open-meteo.com/v1/forecast?latitude={data[0]['lat']}&longitude={data[0]['lon']}&current_weather=true")
                return JSONResponse(content={"status": "success", "temp": w.json()['current_weather']['temperature']})
    except: pass
    return JSONResponse(content={"status": "error"})

@app.post("/geocode")
async def geocode(address: str = Form(...)):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1", headers={'User-Agent': 'TourBuddy'})
            data = res.json()
            if data: return JSONResponse(content={"status": "success", "lat": float(data[0]['lat']), "lon": float(data[0]['lon'])})
    except: pass
    return JSONResponse(content={"status": "error"})

@app.post("/plan_route")
async def plan_route(user_lat: float = Form(...), user_lon: float = Form(...), dest_city: str = Form(...)):
    return JSONResponse(content={"status": "success", "route": [{"step":1, "name":"Start", "lat":user_lat, "lon":user_lon}, {"step":2, "name":dest_city, "lat":user_lat+0.01, "lon":user_lon+0.01}]})

# --- ADMIN DASHBOARD ANALYTICS 📊 ---
@app.get("/admin_stats")
async def admin_stats():
    if IS_OFFLINE: return JSONResponse(content={"status": "error", "message": "Offline"})
    try:
        u_count = users_col.count_documents({})
        p_count = places_col.count_documents({})
        r_count = reviews_col.count_documents({})
        cat_pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
        cats = list(places_col.aggregate(cat_pipeline))
        city_pipeline = [{"$group": {"_id": "$city", "count": {"$sum": 1}}},{"$sort": {"count": -1}},{"$limit": 5}]
        cities = list(places_col.aggregate(city_pipeline))
        return JSONResponse(content={
            "status": "success",
            "counts": [u_count, p_count, r_count],
            "cat_labels": [c["_id"].title() for c in cats],
            "cat_values": [c["count"] for c in cats],
            "city_labels": [c["_id"].title() for c in cities],
            "city_values": [c["count"] for c in cities]
        })
    except Exception as e:
        return JSONResponse(content={"status": "error"})

# --- ADMIN CMS API (NEW SECTION ✅) ---
@app.get("/api/cities")
async def get_cities():
    cities = places_col.distinct("city")
    return JSONResponse(cities)

@app.get("/admin/api/items/{city}/{category}")
async def get_admin_items(city: str, category: str, token: str):
    if token not in SESSIONS: return JSONResponse([])
    items = list(places_col.find({
        "city": {"$regex": f"^{city}$", "$options": "i"},
        "category": category
    }, {'_id': 0}))
    return JSONResponse(items)

@app.post("/admin/api/edit/{city}/{category}/{id}")
async def edit_item(city: str, category: str, id: str, 
                    name: str = Form(...), desc: str = Form(...), 
                    rating: str = Form(...), budget: str = Form(...),
                    lat: float = Form(0), lon: float = Form(0),
                    token: str = Form(...)):
    
    if token not in SESSIONS: return JSONResponse({"status": "error"})
    
    places_col.update_one({"id": id}, {"$set": {
        "name": name, "desc": desc, "budget": budget, "lat": lat, "lon": lon
    }})
    return JSONResponse({"status": "success"})

@app.post("/admin/api/upload/{city}/{category}/{id}")
async def upload_admin_image(id: str, token: str = Form(...), img_data: str = Form(...)):
    if token not in SESSIONS: return JSONResponse({"status": "error"})
    
    try:
        final_data = f"data:image/jpeg;base64,{img_data}"
        res = cloudinary.uploader.upload(final_data)
        new_url = res.get("url")
        places_col.update_one({"id": id}, {"$set": {"img": new_url}})
        return JSONResponse({"status": "success", "url": new_url})
    except Exception as e:
        print(f"Upload Error: {e}")
        return JSONResponse({"status": "error"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)