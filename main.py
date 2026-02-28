from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import random

app = FastAPI()

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
# MENU STRUCTURE
# -------------------------
MENUS = {

    "main": {
        "prompt": (
            "Welcome to IRCTC IVR System.\n"
            "Press 1 for Ticket Booking.\n"
            "Press 2 for PNR Status.\n"
            "Press 3 to Cancel Ticket.\n"
            "Press 4 for Train Schedule.\n"
            "Press 5 to Check Seat Availability.\n"
            "Press 9 to Talk to Customer Care."
        ),
        "options": {
            "1": "booking",
            "2": "pnr",
            "3": "cancel",
            "4": "schedule",
            "5": "availability_train",
            "9": "agent"
        }
    },

    "booking": {
        "prompt": (
            "Ticket Booking Menu.\n"
            "Press 1 for General Ticket.\n"
            "Press 2 for Tatkal Ticket.\n"
            "Press 0 to return to Main Menu."
        ),
        "options": {
            "1": "general_source",
            "2": "tatkal_ticket",
            "0": "main"
        }
    },

    "tatkal_ticket": {
        "prompt": "Tatkal booking is available via IRCTC website only.",
        "options": {}
    },

    "agent": {
        "prompt": "Connecting you to IRCTC Customer Care Executive.",
        "options": {}
    },

"general_source": {
    "prompt": (
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
    "options": {
        "1": "general_destination",
        "2": "general_destination",
        "3": "general_destination",
        "4": "general_destination",
        "5": "general_destination",
        "6": "general_destination",
        "7": "general_destination",
        "8": "general_destination",
        "9": "general_destination"
    }
},

"general_destination": {
    "prompt": (
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
    "options": {
        "1": "general_train_select",
        "2": "general_train_select",
        "3": "general_train_select",
        "4": "general_train_select",
        "5": "general_train_select",
        "6": "general_train_select",
        "7": "general_train_select",
        "8": "general_train_select",
        "9": "general_train_select"
    }
},
    "booking_success": {"prompt": "Your ticket has been successfully booked.", "options": {}},

    # PNR / Cancel / Schedule / Seat
    "pnr": {"prompt": "Enter your 10-digit PNR number.", "options": {}},
    "cancel": {"prompt": "Enter your Booking ID.", "options": {}},
    "schedule": {"prompt": "Enter Train Number to check schedule.", "options": {}},
    "availability_train": {"prompt": "Enter Train Number.", "options": {}},
    "availability_date": {"prompt": "Enter Journey Date (YYYYMMDD).", "options": {}},
}


# -------------------------
# START CALL
# -------------------------
@app.post("/ivr/start")
def start_call(request: StartRequest):
    session_id = f"SIM_{random.randint(100000, 999999)}"

    sessions[session_id] = {
        "current_menu": "main",
        "data": {}
    }

    return {
        "session_id": session_id,
        "menu": "main",
        "prompt": MENUS["main"]["prompt"]
    }


# -------------------------
# HANDLE INPUT
# -------------------------
@app.post("/ivr/input")
def handle_input(request: InputRequest):

    if request.session_id not in sessions:
        return {"error": "Invalid session"}

    session = sessions[request.session_id]
    current_menu = session["current_menu"]

    # =============================
    # GENERAL BOOKING FLOW
    # =============================

    if current_menu == "general_source":
        session["data"]["source"] = request.digit
        session["current_menu"] = "general_destination"
        return {"menu": "general_destination", "prompt": MENUS["general_destination"]["prompt"]}

    if current_menu == "general_destination":
        source = session["data"]["source"]
        destination = request.digit

        FAKE_TRAIN_DB = {
            ("101", "102"): ["1 - 12627 Karnataka Express", "2 - 12760 Charminar Express"]
        }

        trains = FAKE_TRAIN_DB.get((source, destination))

        if not trains:
            del sessions[request.session_id]
            return {"action": "hangup", "message": "No trains available for selected route."}

        session["data"]["trains"] = trains
        session["current_menu"] = "general_train_select"

        train_list = "\n".join(trains)
        return {
            "menu": "general_train_select",
            "prompt": f"Available Trains:\n{train_list}\nSelect train number."
        }

    if current_menu == "general_train_select":
        session["data"]["selected_train"] = request.digit
        session["current_menu"] = "general_date"
        return {"menu": "general_date", "prompt": MENUS["general_date"]["prompt"]}

    if current_menu == "general_date":
        session["data"]["date"] = request.digit
        session["current_menu"] = "general_confirm"
        return {"menu": "general_confirm", "prompt": MENUS["general_confirm"]["prompt"]}

    # =============================
    # PNR STATUS
    # =============================
    if current_menu == "pnr":
        FAKE_PNR_DB = {
            "1234567890": "Confirmed - Coach S3 Seat 45",
            "9876543210": "Waiting List - WL 12"
        }
        status = FAKE_PNR_DB.get(request.digit, "Invalid PNR Number.")
        del sessions[request.session_id]
        return {"action": "hangup", "message": f"PNR Status:\n{status}"}

    # =============================
    # CANCEL TICKET
    # =============================
    if current_menu == "cancel":
        FAKE_BOOKING_DB = {"5555": True, "9999": True}
        if request.digit in FAKE_BOOKING_DB:
            message = "Your ticket has been successfully cancelled."
        else:
            message = "Invalid Booking ID."
        del sessions[request.session_id]
        return {"action": "hangup", "message": message}

    # =============================
    # TRAIN SCHEDULE
    # =============================
    if current_menu == "schedule":
        FAKE_SCHEDULE_DB = {
            "12627": "Departs 06:00 AM - Arrives 06:30 PM",
            "12760": "Departs 05:00 PM - Arrives 07:00 AM"
        }
        schedule = FAKE_SCHEDULE_DB.get(request.digit, "Train not found.")
        del sessions[request.session_id]
        return {"action": "hangup", "message": f"Train Schedule:\n{schedule}"}

    # =============================
    # SEAT AVAILABILITY
    # =============================
    if current_menu == "availability_train":
        session["data"]["train"] = request.digit
        session["current_menu"] = "availability_date"
        return {"menu": "availability_date", "prompt": MENUS["availability_date"]["prompt"]}

    if current_menu == "availability_date":
        train = session["data"]["train"]

        FAKE_SEAT_DB = {
            "12627": {"20240615": 45, "20240616": 12},
            "12760": {"20240615": 0}
        }

        seats = FAKE_SEAT_DB.get(train, {}).get(request.digit)

        if seats is None:
            message = "No data available."
        elif seats == 0:
            message = "Seats are full. Waiting list applies."
        else:
            message = f"{seats} seats are available."

        del sessions[request.session_id]
        return {"action": "hangup", "message": message}

    # =============================
    # NORMAL MENU NAVIGATION
    # =============================
    options = MENUS[current_menu]["options"]

    if request.digit in options:
        next_menu = options[request.digit]
        session["current_menu"] = next_menu

        if MENUS[next_menu]["options"] == {}:
            message = MENUS[next_menu]["prompt"]
            del sessions[request.session_id]
            return {"action": "hangup", "message": message}

        return {"menu": next_menu, "prompt": MENUS[next_menu]["prompt"]}

    return {"error": "Invalid input. Please try again."}