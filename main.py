from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel, EmailStr, validator, root_validator
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from datetime import datetime, timedelta, timezone

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = "game_data.json"

def load_data():
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "Game1": {"users": {}, "scores": [], "user_counter": 0},
        "Game2": {"users": {}, "scores": [], "user_counter": 0},
        "Game3": {"users": {}, "scores": [], "user_counter": 0},
        "AR": {"users": {}, "scores": [], "user_counter": 0}
    }

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data_store, f, indent=2, default=str)

data_store = load_data()

# Models
class UserInput(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: str

    @root_validator(pre=True)
    def empty_string_to_none(cls, values):
        if "email" in values and values["email"] == "":
            values["email"] = None
        return values

class ScoreInput(BaseModel):
    player_id: str
    score: int

    @validator('player_id', pre=True)
    def convert_to_string(cls, v):
        return str(v)

@app.post(f"/{game_name.lower()}/save_user")
def save_user(data: UserInput):
    game = data_store[game_name]

    if "user_counter" not in game:
        game["user_counter"] = 0

    # Check for existing user
    for uid, user in game["users"].items():
        if user["phone"] == data.phone or (data.email and user["email"] == data.email):
            return {"message": f"{game_name} user already exists", "player_id": uid}

    _id = str(game["user_counter"])
    game["user_counter"] += 1

    IST = timezone(timedelta(hours=5, minutes=30))  # ⏰ Indian Standard Time

    game["users"][_id] = {
        "id": _id,
        "name": data.name,
        "email": data.email,
        "phone": data.phone,
        "scores": [],
        "created_at": datetime.now(IST).isoformat()
    }

    save_data()
    return {"message": f"{game_name} user saved", "player_id": _id}


    @app.patch(f"/{game_name.lower()}/save_score")
    def save_score(data: ScoreInput = Body(...)):
        game = data_store[game_name]
        player_id = data.player_id

        if player_id not in game["users"]:
            raise HTTPException(status_code=404, detail="User not found")

        user = game["users"][player_id]

        score_entry = {
            "player_id": player_id,
            "username": user["name"],
            "email": user["email"],
            "phone": user["phone"],
            "finalScore": data.score
        }

        game["scores"].append(score_entry)
        user["scores"].append(data.score)

        save_data()

        return {
            "message": f"{game_name} score saved",
            "score": score_entry,
            "updated_user_scores": user["scores"]
        }

    @app.get(f"/{game_name.lower()}/get_data")
    def get_data():
        game = data_store[game_name]
        users = []

        for user in game["users"].values():
            user_copy = user.copy()
            user_copy["score"] = max(user["scores"]) if user["scores"] else "No Score"
            users.append(user_copy)

        return {
            "users": users,
            "scores": game["scores"]
        }

    @app.delete(f"/{game_name.lower()}/clear_data")
    def clear_data():
        game = data_store[game_name]
        game["users"] = {}
        game["scores"] = []
        game["user_counter"] = 0
        save_data()
        return {"message": f"{game_name} data cleared successfully"}

# Register all games
for game in ["Game1", "Game2", "Game3", "AR"]:
    register_game_routes(game)

@app.delete("/clear_all_data")
def clear_all_data():
    global data_store
    data_store = load_data()
    save_data()
    return {"message": "All game data cleared successfully"}

@app.get("/")
def home():
    return {"message": "FastAPI backend is live 🚀"}

templates = Jinja2Templates(directory="templates")

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})
