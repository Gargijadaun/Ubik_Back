from fastapi import FastAPI, HTTPException, Body, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, field_validator, model_validator
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
        "AR": {"users": {}, "phase_times": [], "user_counter": 0}
    }

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data_store, f, indent=2, default=str)

data_store = load_data()

# Pydantic Models
class UserInput(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: str

    @field_validator('phone', mode='before')
    @classmethod
    def convert_phone_to_string(cls, v):
        return str(v)

    @model_validator(mode='before')
    @classmethod
    def empty_string_to_none(cls, values):
        if "email" in values and values["email"] == "":
            values["email"] = None
        return values

class ScoreInput(BaseModel):
    player_id: str
    score: int
    discount: Optional[float] = None

    @field_validator('player_id', mode='before')
    @classmethod
    def convert_to_string(cls, v):
        return str(v)

    @field_validator('discount')
    @classmethod
    def validate_discount(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Discount must be between 0 and 100")
        return v

class ARPhaseTimeInput(BaseModel):
    player_id: str
    phase: str
    time_spent: float

    @field_validator('player_id', mode='before')
    @classmethod
    def convert_to_string(cls, v):
        return str(v)

    @field_validator('phase')
    @classmethod
    def validate_phase(cls, v):
        if v not in ["Girl", "Boy", "Aged Girl"]:
            raise ValueError("Phase must be 'Girl', 'Boy', or 'Aged Girl'")
        return v

    @field_validator('time_spent')
    @classmethod
    def validate_time_spent(cls, v):
        if v < 0:
            raise ValueError("Time spent cannot be negative")
        return v

# Register dynamic game routes
def register_game_routes(game_name: str):
    def create_user_route(prefix: str = ""):
        @app.post(f"/{game_name.lower()}/{prefix}save_user")
        def save_user(data: UserInput):
            game = data_store[game_name]
            if "user_counter" not in game:
                game["user_counter"] = 0

            for uid, user in game["users"].items():
                if user["phone"] == data.phone or (data.email and user["email"] == data.email):
                    return {"message": f"{game_name} user already exists", "player_id": uid}

            _id = str(game["user_counter"])
            game["user_counter"] += 1

            IST = timezone(timedelta(hours=5, minutes=30))
            variant = (
                "Doctor 1" if prefix == "doctor1/" else
                "Doctor 2" if prefix == "doctor2/" else
                "Main"
            )

            game["users"][_id] = {
                "id": _id,
                "name": data.name,
                "email": data.email,
                "phone": data.phone,
                "scores": [],
                "variant": variant,
                "created_at": datetime.now(IST).isoformat(),
                "game": game_name
            }

            save_data()
            return {"message": f"{game_name} user saved", "player_id": _id}

    def create_score_route(prefix: str = ""):
        if game_name == "AR":
            @app.post(f"/{game_name.lower()}/{prefix}save_phase_time")
            def save_phase_time(data: ARPhaseTimeInput = Body(...)):
                game = data_store[game_name]
                player_id = data.player_id

                if player_id not in game["users"]:
                    raise HTTPException(status_code=404, detail="User not found")

                user = game["users"][player_id]
                phase_time_entry = {
                    "player_id": player_id,
                    "username": user["name"],
                    "email": user["email"],
                    "phone": user["phone"],
                    "phase": data.phase,
                    "time_spent": data.time_spent,
                    "variant": user["variant"],
                    "timestamp": datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
                }

                game["phase_times"].append(phase_time_entry)
                user["scores"].append({
                    "phase": data.phase,
                    "time_spent": data.time_spent
                })

                save_data()
                return {
                    "message": f"{game_name} phase time saved",
                    "phase_time": phase_time_entry,
                    "updated_user_phase_times": user["scores"]
                }
        else:
            @app.patch(f"/{game_name.lower()}/{prefix}save_score")
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

                if hasattr(data, "discount") and data.discount is not None:
                    score_entry["discount"] = data.discount

                game["scores"].append(score_entry)
                user_score = {"score": data.score}
                if hasattr(data, "discount") and data.discount is not None:
                    user_score["discount"] = data.discount
                user["scores"].append(user_score)

                save_data()
                return {
                    "message": f"{game_name} score saved",
                    "score": score_entry,
                    "updated_user_scores": user["scores"]
                }

    def create_get_data_route(prefix: str = ""):
        @app.get(f"/{game_name.lower()}/{prefix}get_data")
        def get_data(
            name: Optional[str] = Query(None),
            player_id: Optional[str] = Query(None),
            start_time: Optional[str] = Query(None),
            end_time: Optional[str] = Query(None)
        ):
            game = data_store[game_name]
            users = []

            for user in game["users"].values():
                if name and name.lower() not in user["name"].lower():
                    continue
                if player_id and user["id"] != player_id:
                    continue
                if start_time or end_time:
                    try:
                        created_at = datetime.fromisoformat(user["created_at"])
                    except ValueError:
                        continue
                    if start_time:
                        start_dt = datetime.fromisoformat(start_time)
                        if created_at < start_dt:
                            continue
                    if end_time:
                        end_dt = datetime.fromisoformat(end_time)
                        if created_at > end_dt:
                            continue
                user_copy = user.copy()
                
                if game_name == "AR":
                    # Initialize phase times with 0 for each phase
                    phase_times = {"Girl": 0.0, "Boy": 0.0, "Aged Girl": 0.0}
                    # Aggregate time spent for each phase
                    for entry in user["scores"]:
                        if "phase" in entry and "time_spent" in entry:
                            phase_times[entry["phase"]] = entry["time_spent"]
                    user_copy["phase_times"] = phase_times
                    # Calculate total time for display
                    user_copy["total_time"] = sum(phase_times.values())
                else:
                    if user["scores"]:
                        if isinstance(user["scores"][0], dict):
                            user_copy["score"] = max([s["score"] for s in user["scores"]])
                        else:
                            user_copy["score"] = max(user["scores"])
                    else:
                        user_copy["score"] = "No Score"

                if "variant" not in user_copy:
                    user_copy["variant"] = "Main"
                users.append(user_copy)

            return {
                "users": users,
                "data": game["phase_times" if game_name == "AR" else "scores"]
            }

    for prefix in ["", "doctor1/", "doctor2/"]:
        create_user_route(prefix)
        create_score_route(prefix)
        create_get_data_route(prefix)

    @app.delete(f"/{game_name.lower()}/clear_data")
    def clear_data():
        game = data_store[game_name]
        game["users"] = {}
        game["scores" if game_name != "AR" else "phase_times"] = []
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
    for game in data_store:
        game["users"] = {}
        game["scores" if game != "AR" else "phase_times"] = []
        game["user_counter"] = 0
    save_data()
    return {"message": "All game data cleared successfully"}

@app.get("/")
def home():
    return {"message": "FastAPI backend is live 🚀"}

templates = Jinja2Templates(directory="templates")

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})