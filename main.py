from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel, EmailStr, field_validator, ValidationError
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data_store, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save data to {DATA_FILE}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save data")

# Load data
data_store = load_data()

# Models
class UserInput(BaseModel):
    name: str
    email: Optional[EmailStr] = None  # Email is optional
    phone: str

    @field_validator('name', 'phone')
    def check_not_empty(cls, v, field):
        if not v or v.strip() == "":
            raise ValueError(f"{field.name} cannot be empty")
        return v

class ScoreInput(BaseModel):
    player_id: str
    score: int

    @field_validator('player_id', mode='before')
    def convert_to_string(cls, v):
        if v is None:
            raise ValueError("player_id cannot be null")
        return str(v)

def register_game_routes(game_name: str):
    @app.post(f"/{game_name.lower()}/save_user")
    async def save_user(data: UserInput, request: Request):
        try:
            logger.info(f"Received save_user request for {game_name}: {data.dict()}")
            game = data_store[game_name]

            if "user_counter" not in game:
                game["user_counter"] = 0

            # Check if user exists by phone or email (if provided)
            for uid, user in game["users"].items():
                if user["phone"] == data.phone or (data.email and user.get("email") == data.email):
                    return {"message": f"{game_name} user already exists", "player_id": uid}

            # Generate new user ID
            _id = str(game["user_counter"])
            game["user_counter"] += 1

            game["users"][_id] = {
                "id": _id,
                "name": data.name,
                "email": data.email,  # None if not provided
                "phone": data.phone,
                "scores": []
            }

            save_data()
            return {"message": f"{game_name} user saved", "player_id": _id}
        except ValidationError as e:
            logger.error(f"Validation error in save_user for {game_name}: {str(e)}")
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error in save_user for {game_name}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.patch(f"/{game_name.lower()}/save_score")
    async def save_score(data: ScoreInput = Body(...), request: Request = None):
        try:
            logger.info(f"Received save_score request for {game_name}: {data.dict()}")
            game = data_store[game_name]
            player_id = data.player_id

            if player_id not in game["users"]:
                raise HTTPException(status_code=404, detail="User not found")

            user = game["users"][player_id]

            score_entry = {
                "player_id": player_id,
                "username": user["name"],
                "email": user.get("email", None),  # Handle missing email
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
        except ValidationError as e:
            logger.error(f"Validation error in save_score for {game_name}: {str(e)}")
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error in save_score for {game_name}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get(f"/{game_name.lower()}/get_data")
    async def get_data():
        try:
            game = data_store[game_name]
            users = []

            for user in game["users"].values():
                user_copy = user.copy()
                user_copy["email"] = user.get("email", "No email")  # Fallback for display
                user_copy["score"] = max(user["scores"]) if user["scores"] else "No Score"
                users.append(user_copy)

            return {
                "users": users,
                "scores": game["scores"]
            }
        except Exception as e:
            logger.error(f"Error in get_data for {game_name}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.delete(f"/{game_name.lower()}/clear_data")
    async def clear_data():
        try:
            game = data_store[game_name]
            game["users"] = {}
            game["scores"] = []
            game["user_counter"] = 0
            save_data()
            return {"message": f"{game_name} data cleared successfully"}
        except Exception as e:
            logger.error(f"Error in clear_data for {game_name}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

# Register routes for all games
for game in ["Game1", "Game2", "Game3", "AR"]:
    register_game_routes(game)

@app.delete("/clear_all_data")
async def clear_all_data():
    try:
        global data_store
        data_store = {
            "Game1": {"users": {}, "scores": [], "user_counter": 0},
            "Game2": {"users": {}, "scores": [], "user_counter": 0},
            "Game3": {"users": {}, "scores": [], "user_counter": 0},
            "AR": {"users": {}, "scores": [], "user_counter": 0}
        }
        save_data()
        return {"message": "All game data cleared successfully"}
    except Exception as e:
        logger.error(f"Error in clear_all_data: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/")
async def home():
    return {"message": "FastAPI backend is live 🚀"}

# Admin template route
templates = Jinja2Templates(directory="templates")

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin(request: Request):
    try:
        return templates.TemplateResponse("admin.html", {"request": request})
    except Exception as e:
        logger.error(f"Error serving admin page: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to render admin page")