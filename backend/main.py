# main.py
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import random
from datetime import datetime, timedelta

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# SESSION STORAGE
# -------------------------
sessions = {}

# -------------------------
# REQUEST MODELS
# -------------------------
class StartRequest(BaseModel):
    caller_number: str

class InputRequest(BaseModel):
    session_id: str
    value: str  # Can be a digit or text input

# -------------------------
# MOCK DATA
# -------------------------
STATIONS = {
    "1": "Hyderabad Deccan",
    "2": "Chennai Central",
    "3": "New Delhi",
    "4": "Mumbai CSMT",
    "5": "Howrah Junction",
    "6": "Bengaluru City",
    "7": "Secunderabad",
    "8": "Vijayawada",
    "9": "Ahmedabad"
}

TRAINS = [
    "1 - 12627 Karnataka Express",
    "2 - 12760 Charminar Express",
    "3 - 12841 Coromandel Express"
]

# -------------------------
# MENUS
# -------------------------
MAIN_MENU = (
    "Welcome to IRCTC IVR System.\n"
    "Press 1 for Ticket Booking.\n"
    "Press 2 for PNR Status.\n"
    "Press 3 to Cancel Ticket.\n"
    "Press 4 for Train Schedule.\n"
    "Press 5 to Check Seat Availability.\n"
    "Press 9 to Talk to Customer Care."
)

# -------------------------
# INTENT DETECTION
# -------------------------
def detect_intent(digit):
    return {
        "1": "book_ticket",
        "2": "pnr_status",
        "3": "cancel_ticket",
        "4": "train_schedule",
        "5": "seat_availability",
        "9": "agent"
    }.get(digit)

# -------------------------
# START CALL
# -------------------------
@app.post("/ivr/start")
def start_call(request: StartRequest):
    session_id = f"SIM_{random.randint(100000, 999999)}"
    sessions[session_id] = {
        "intent": None,
        "stage": "main",
        "data": {}
    }
    return {"session_id": session_id, "prompt": MAIN_MENU}

# -------------------------
# HANDLE INPUT
# -------------------------
@app.post("/ivr/input")
def handle_input(request: InputRequest):
    if request.session_id not in sessions:
        return {"error": "Invalid session"}
    
    session = sessions[request.session_id]
    stage = session["stage"]
    value = request.value.strip()

    # -------------------------
    # MAIN MENU
    # -------------------------
    if stage == "main":
        intent = detect_intent(value)
        session["intent"] = intent
        if intent == "book_ticket":
            session["stage"] = "source"
            return {"prompt": "Enter Source Station:\n" + "\n".join([f"{k}. {v}" for k, v in STATIONS.items()])}
        if intent == "pnr_status":
            session["stage"] = "pnr_number"
            return {"prompt": "Enter your 10-digit PNR number."}
        if intent == "cancel_ticket":
            session["stage"] = "cancel_train"
            return {"prompt": "Enter Train Number to cancel ticket."}
        if intent == "train_schedule":
            session["stage"] = "schedule_train"
            return {"prompt": "Enter Train Number to check schedule."}
        if intent == "seat_availability":
            session["stage"] = "availability_train"
            return {"prompt": "Enter Train Number to check seat availability."}
        if intent == "agent":
            del sessions[request.session_id]
            return {"prompt": "Connecting to IRCTC Customer Care...", "action": "hangup"}

        return {"error": "Invalid input at main menu."}

    # -------------------------
    # BOOKING FLOW
    # -------------------------
    if session["intent"] == "book_ticket":
        if stage == "source":
            if value not in STATIONS:
                return {"prompt": "Invalid source. Try again."}
            session["data"]["source"] = STATIONS[value]
            session["stage"] = "destination"
            return {"prompt": "Enter Destination Station:\n" + "\n".join([f"{k}. {v}" for k, v in STATIONS.items()])}

        if stage == "destination":
            if value not in STATIONS:
                return {"prompt": "Invalid destination. Try again."}
            session["data"]["destination"] = STATIONS[value]
            session["stage"] = "date"
            return {"prompt": "Select Journey Date:\n1. Today\n2. Tomorrow\n3. Day After Tomorrow"}

        if stage == "date":
            today = datetime.today()
            if value == "1":
                journey_date = today
            elif value == "2":
                journey_date = today + timedelta(days=1)
            elif value == "3":
                journey_date = today + timedelta(days=2)
            else:
                return {"prompt": "Invalid date option."}
            session["data"]["date"] = journey_date.strftime("%Y-%m-%d")
            session["stage"] = "train_select"
            return {"prompt": "Available Trains:\n" + "\n".join(TRAINS) + "\nSelect train number."}

        if stage == "train_select":
            try:
                idx = int(value) - 1
                selected_train = TRAINS[idx]
            except:
                return {"prompt": "Invalid train selection."}
            del sessions[request.session_id]
            return {"prompt": f"Your ticket for {selected_train} from {session['data']['source']} to {session['data']['destination']} on {session['data']['date']} has been booked successfully.", "action": "hangup"}

    # -------------------------
    # PNR STATUS FLOW
    # -------------------------
    if session["intent"] == "pnr_status" and stage == "pnr_number":
        del sessions[request.session_id]
        return {"prompt": f"PNR {value} Status: Confirmed", "action": "hangup"}

    # -------------------------
    # CANCEL TICKET FLOW
    # -------------------------
    if session["intent"] == "cancel_ticket" and stage == "cancel_train":
        del sessions[request.session_id]
        return {"prompt": f"Ticket for Train {value} has been canceled.", "action": "hangup"}

    # -------------------------
    # TRAIN SCHEDULE FLOW
    # -------------------------
    if session["intent"] == "train_schedule" and stage == "schedule_train":
        session["stage"] = "schedule_date"
        session["data"]["train"] = value
        return {"prompt": "Enter Journey Date (YYYY-MM-DD) to check schedule."}

    if session["intent"] == "train_schedule" and stage == "schedule_date":
        train = session["data"]["train"]
        del sessions[request.session_id]
        return {"prompt": f"Train {train} schedule on {value}: Seats available.", "action": "hangup"}

    # -------------------------
    # SEAT AVAILABILITY FLOW
    # -------------------------
    if session["intent"] == "seat_availability":
        if stage == "availability_train":
            session["data"]["train"] = value
            session["stage"] = "availability_date"
            return {"prompt": "Enter Journey Date (YYYY-MM-DD) to check seat availability."}
        if stage == "availability_date":
            train = session["data"]["train"]
            del sessions[request.session_id]
            return {"prompt": f"Seats for Train {train} on {value}: Available", "action": "hangup"}

    return {"error": "Invalid input."}