# 🌍 TourBuddy: AI-Powered Exploration Engine

> **"Stop Planning, Start Experiencing."**

[![Live Demo](https://img.shields.io/badge/Live_Demo-Click_Here-2dd4bf?style=for-the-badge&logo=render)](https://tourbuddy-ejwk.onrender.com)
[![GitHub Repo](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github)](https://github.com/snepnap/TourBuddy.git)

TourBuddy is an intelligent travel companion built to solve "Travel Burnout." Unlike generic maps, TourBuddy uses **Generative AI (Google Gemini)**, **"Vibe" tagging**, and **predictive time modeling** to curate the perfect trip based on relevance, not just popularity.

---

## 🚨 The Problem
Traditional travel apps have three critical blind spots:
1.  **Contextual Blindness:** A 4.8-star rating doesn't tell you if a place is "Adventure" or "Relaxing."
2.  **The Time-Blindness Trap:** Travelers overpack itineraries because they lack realistic data on how long a visit actually takes.
3.  **Discovery Fatigue:** Switching between Google Maps, blogs, and review sites is exhausting.

## 💡 The Solution
**TourBuddy** acts as a smart layer over traditional maps. It provides:
* **⏳ Time-at-Venue Estimates:** "Avg time spent: 2.5 hours" to help you plan better.
* **🏷️ Vibe-Based Tagging:** Search by mood (e.g., *#Spiritual*, *#HighEnergy*, *#Chill*).
* **🤖 AI-Powered Content:** Instantly generates engaging descriptions for new spots using Google Gemini AI.

---

## ⚙️ Tech Stack

| Component | Technology |
| :--- | :--- |
| **Backend** | Python (FastAPI) |
| **Database** | MongoDB (NoSQL) |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **AI Engine** | Google Gemini API (Generative AI) |
| **Maps** | Leaflet.js & OpenStreetMap |
| **Media** | Cloudinary (Image Optimization) |

---

## 🚀 Key Features

### 1. 🤖 AI Description Generator
* **One-Click Magic:** When adding a new spot, users can click **"✨ Write with AI"**.
* **How it works:** It sends the place name and "vibe" to Google Gemini, which returns a catchy, 2-sentence description instantly.

### 2. 🧭 Smart Discovery & Navigation
* **Live Distance Tracking:** Automatically calculates the distance from the user's current GPS location to the destination.
* **Direct Navigation:** "Nav ↗" button opens the route directly in Google Maps.

### 3. 🎨 Dynamic UI with Dark/Light Mode
* A beautiful, glassmorphism-inspired UI.
* Fully responsive toggle between **Day Mode** ☀ and **Night Mode** ☾.

### 4. 🛡️ Admin & Analytics Dashboard
* **Real-time Stats:** Track total users, places, and reviews.
* **Content Management:** Admins can edit details, update images, and manage user reviews.
* *Note: The Admin button is hidden for normal users.*

---

## 🛠️ Installation & Local Setup

If you want to run this project locally, follow these steps:

### 1. Clone the Repository
```bash
git clone [https://github.com/snepnap/TourBuddy.git](https://github.com/snepnap/TourBuddy.git)
cd TourBuddy
