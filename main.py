from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import random
from datetime import datetime, timedelta
import speech_recognition as sr
import speech_recognition as sr
print(sr.Microphone.list_microphone_names())
def listen_voice():

    recognizer = sr.Recognizer()

    with sr.Microphone() as source:

        print("🎤 Adjusting for background noise...")
        recognizer.adjust_for_ambient_noise(source, duration=1)

        print("🎤 Speak now...")

        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=4)
        except:
            print("No speech detected")
            return ""

    try:
        text = recognizer.recognize_google(audio)
        print("You said:", text)
        return text.lower()

    except sr.UnknownValueError:
        print("❌ Could not understand voice")
        return ""

    except sr.RequestError:
        print("❌ Speech service error")
        return ""
app = FastAPI()
@app.get("/")
def home():
    return {
        "project": "AI Based IRCTC IVR System",
        "status": "Running"
    }

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
    digit: str


# -------------------------
# INTENT DETECTION
# -------------------------
def detect_intent(digit):
    intent_map = {
        "1": "book_ticket",
        "2": "pnr_status",
        "3": "cancel_ticket",
        "4": "train_schedule",
        "5": "seat_availability",
        "9": "agent"
    }
    return intent_map.get(digit)


# -------------------------
# MOCK TRAIN API
# -------------------------
def get_available_trains(source, destination, date):
    return [
        "1 - 12627 Karnataka Express",
        "2 - 12760 Charminar Express",
        "3 - 12841 Coromandel Express"
    ]


# -------------------------
# MENUS
# -------------------------
MENUS = {

    "main": (
        "Welcome to IRCTC IVR System.\n"
        "Press 1 for Ticket Booking.\n"
        "Press 2 for PNR Status.\n"
        "Press 3 to Cancel Ticket.\n"
        "Press 4 for Train Schedule.\n"
        "Press 5 to Check Seat Availability.\n"
        "Press 9 to Talk to Customer Care."
    ),

    "booking": (
        "Ticket Booking Menu.\n"
        "Press 1 for General Ticket.\n"
        "Press 2 for Tatkal Ticket.\n"
        "Press 0 to return to Main Menu."
    ),

    "source": (
        "Select Source Station.\n"
        "Press 1 for Hyderabad Deccan.\n"
        "Press 2 for Chennai Central.\n"
        "Press 3 for New Delhi.\n"
        "Press 4 for Mumbai CSMT.\n"
        "Press 5 for Howrah Junction.\n"
        "Press 6 for Bengaluru City.\n"
        "Press 7 for Secunderabad.\n"
        "Press 8 for Vijayawada.\n"
        "Press 9 for Ahmedabad."
    ),

    "destination": (
        "Select Destination Station.\n"
        "Press 1 for Hyderabad Deccan.\n"
        "Press 2 for Chennai Central.\n"
        "Press 3 for New Delhi.\n"
        "Press 4 for Mumbai CSMT.\n"
        "Press 5 for Howrah Junction.\n"
        "Press 6 for Bengaluru City.\n"
        "Press 7 for Secunderabad.\n"
        "Press 8 for Vijayawada.\n"
        "Press 9 for Ahmedabad."
    ),

    "date": (
        "Select Journey Date.\n"
        "Press 1 for Today.\n"
        "Press 2 for Tomorrow.\n"
        "Press 3 for Day After Tomorrow."
    ),

    "pnr": "Enter your 10-digit PNR number.",

    "cancel": "Enter your Booking ID.",

    "schedule": "Enter Train Number to check schedule.",

    "availability_train": "Enter Train Number.",

    "availability_date": "Enter Journey Date (YYYYMMDD)."
}


# -------------------------
# START CALL
# -------------------------
@app.post("/ivr/start")
def start_call(request: StartRequest):

    session_id = f"SIM_{random.randint(100000,999999)}"

    sessions[session_id] = {
        "intent": None,
        "stage": "main",
        "data": {}
    }

    return {
        "session_id": session_id,
        "menu": "main",
        "prompt": MENUS["main"]
    }


# -------------------------
# HANDLE INPUT
# -------------------------
@app.post("/ivr/input")
def handle_input(request: InputRequest):

    if request.session_id not in sessions:
        return {"error": "Invalid session"}

    session = sessions[request.session_id]
    stage = session["stage"]

    # -------------------------
    # MAIN MENU
    # -------------------------
    if stage == "main":

        intent = detect_intent(request.digit)
        session["intent"] = intent

        if intent == "book_ticket":
            session["stage"] = "ticket_type"
            return {"menu": "booking", "prompt": MENUS["booking"]}

        if intent == "pnr_status":
            session["stage"] = "pnr"
            return {"menu": "pnr", "prompt": MENUS["pnr"]}

        if intent == "cancel_ticket":
            session["stage"] = "cancel"
            return {"menu": "cancel", "prompt": MENUS["cancel"]}

        if intent == "train_schedule":
            session["stage"] = "schedule"
            return {"menu": "schedule", "prompt": MENUS["schedule"]}

        if intent == "seat_availability":
            session["stage"] = "availability_train"
            return {"menu": "availability_train", "prompt": MENUS["availability_train"]}

        if intent == "agent":
            del sessions[request.session_id]
            return {"action": "hangup", "message": "Connecting you to IRCTC Customer Care Executive."}

    # -------------------------
    # BOOKING FLOW
    # -------------------------
    if stage == "ticket_type":

        if request.digit == "1":
            session["stage"] = "source"
            return {"menu": "source", "prompt": MENUS["source"]}

        if request.digit == "2":
            del sessions[request.session_id]
            return {"action": "hangup", "message": "Tatkal booking available via IRCTC website only."}

    if stage == "source":

        session["data"]["source"] = request.digit
        session["stage"] = "destination"

        return {"menu": "destination", "prompt": MENUS["destination"]}

    if stage == "destination":

        session["data"]["destination"] = request.digit
        session["stage"] = "date"

        return {"menu": "date", "prompt": MENUS["date"]}

    if stage == "date":

        option = request.digit
        today = datetime.today()

        if option == "1":
            journey_date = today
        elif option == "2":
            journey_date = today + timedelta(days=1)
        elif option == "3":
            journey_date = today + timedelta(days=2)
        else:
            return {"error": "Invalid date option"}

        session["data"]["date"] = journey_date.strftime("%Y%m%d")

        trains = get_available_trains(
            session["data"]["source"],
            session["data"]["destination"],
            session["data"]["date"]
        )

        session["data"]["trains"] = trains
        session["stage"] = "train_select"

        train_list = "\n".join(trains)

        return {
            "menu": "train_select",
            "prompt": f"Available Trains:\n{train_list}\nSelect train number."
        }

    if stage == "train_select":

        trains = session["data"]["trains"]
        index = int(request.digit) - 1

        if index >= len(trains):
            return {"error": "Invalid train selection"}

        selected_train = trains[index]

        del sessions[request.session_id]

        return {
            "action": "hangup",
            "message": f"Your ticket for {selected_train} has been booked successfully."
        }

    return {"error": "Invalid input"}