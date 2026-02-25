from fastapi import FastAPI
from pydantic import BaseModel
import random
class StartRequest(BaseModel):
    caller: str
app = FastAPI()

# Session storage
sessions = {}
# -------------------------
# IRCTC IVR MENU STRUCTURE
# -------------------------
MENUS = {

    # -------------------------
    # MAIN MENU
    # -------------------------
    "main": {
        "prompt": (
            "Welcome to IRCTC IVR System. "
            "Press 1 for Ticket Booking. "
            "Press 2 for PNR Status. "
            "Press 3 to Cancel Ticket. "
            "Press 4 for Train Schedule. "
            "Press 5 to Check Seat Availability. "
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

    # -------------------------
    # BOOKING MENU
    # -------------------------
    "booking": {
        "prompt": (
            "Ticket Booking Menu. "
            "Press 1 for General Ticket. "
            "Press 2 for Tatkal Ticket. "
            "Press 0 to go back to Main Menu."
        ),
        "options": {
            "1": "general_ticket",
            "2": "tatkal_ticket",
            "0": "main"
        }
    },

    # -------------------------
    # PNR STATUS MENU
    # -------------------------
    "pnr": {
        "prompt": (
            "Please enter your 10-digit PNR number."
        ),
        "options": {}
    },

    # -------------------------
    # CANCEL TICKET MENU
    # -------------------------
    "cancel": {
        "prompt": (
            "Please enter your Booking ID to cancel your ticket."
        ),
        "options": {}
    },

    # -------------------------
    # TRAIN SCHEDULE MENU
    # -------------------------
    "schedule": {
        "prompt": (
            "Please enter your Train Number to check schedule."
        ),
        "options": {}
    },

    # -------------------------
    # SEAT AVAILABILITY FLOW (ADVANCED)
    # -------------------------
    "availability_train": {
        "prompt": (
            "Please enter your Train Number to check seat availability."
        ),
        "options": {}
    },

    "availability_date": {
        "prompt": (
            "Please enter your Journey Date in YYYYMMDD format."
        ),
        "options": {}
    },

    # -------------------------
    # END STATES
    # -------------------------
    "general_ticket": {
        "prompt": (
            "You selected General Ticket Booking. "
            "Our booking executive will assist you shortly."
        ),
        "options": {}
    },

    "tatkal_ticket": {
        "prompt": (
            "You selected Tatkal Ticket Booking. "
            "Please visit IRCTC website for immediate booking."
        ),
        "options": {}
    },

    "agent": {
        "prompt": (
            "Connecting you to IRCTC Customer Care Executive."
        ),
        "options": {}
    }

}

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
class InputRequest(BaseModel):
    session_id: str
    digit: str


@app.post("/ivr/input")
def handle_input(request: InputRequest):

    if request.session_id not in sessions:
        return {"error": "Invalid session"}

    session = sessions[request.session_id]
    current_menu = session["current_menu"]

    # ---------------------------
    # SEAT AVAILABILITY FLOW
    # ---------------------------

    if current_menu == "availability_train":
        session["data"]["train_number"] = request.digit
        session["current_menu"] = "availability_date"

        return {
            "menu": "availability_date",
            "prompt": MENUS["availability_date"]["prompt"]
        }

    if current_menu == "availability_date":

        train_number = session["data"].get("train_number")
        journey_date = request.digit

        FAKE_SEAT_DB = {
            "12627": {"20240615": 45, "20240616": 12},
            "12015": {"20240615": 0, "20240616": 30}
        }

        seats = FAKE_SEAT_DB.get(train_number, {}).get(journey_date)

        if seats is None:
            message = "No data available for given Train Number or Date."
        elif seats == 0:
            message = "Seats are full. Waiting list applies."
        else:
            message = f"{seats} seats are available."

        del sessions[request.session_id]

        return {
            "action": "hangup",
            "message": message
        }

    # ---------------------------
    # NORMAL MENU FLOW
    # ---------------------------

    options = MENUS[current_menu]["options"]

    if request.digit in options:
        next_menu = options[request.digit]
        session["current_menu"] = next_menu

        # If end state → hangup
        if MENUS[next_menu]["options"] == {}:
            message = MENUS[next_menu]["prompt"]
            del sessions[request.session_id]

            return {
                "action": "hangup",
                "message": message
            }

        return {
            "menu": next_menu,
            "prompt": MENUS[next_menu]["prompt"]
        }

    return {
        "error": "Invalid input. Please try again."
    }
