from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import random
from datetime import datetime, timedelta

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
    value: str

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

# Full schedule for each train
TRAIN_SCHEDULES = {
    "1": {
        "name": "12627 Karnataka Express",
        "from": "New Delhi",
        "to": "Bengaluru City",
        "duration": "40 hrs 30 mins",
        "stops": [
            ("New Delhi",        "Starts", "22:30", "Day 1"),
            ("Mathura Junction", "00:55",  "01:00", "Day 2"),
            ("Agra Cantt",       "01:48",  "01:50", "Day 2"),
            ("Gwalior",          "03:07",  "03:10", "Day 2"),
            ("Jhansi",           "04:45",  "04:55", "Day 2"),
            ("Bhopal",           "08:05",  "08:15", "Day 2"),
            ("Nagpur",           "14:00",  "14:15", "Day 2"),
            ("Secunderabad",     "21:50",  "22:10", "Day 2"),
            ("Bengaluru City",   "09:00",  "Ends",  "Day 3"),
        ]
    },
    "2": {
        "name": "12760 Charminar Express",
        "from": "Hyderabad Deccan",
        "to": "Chennai Central",
        "duration": "13 hrs 5 mins",
        "stops": [
            ("Hyderabad Deccan", "Starts", "18:10", "Day 1"),
            ("Secunderabad",     "18:45",  "18:50", "Day 1"),
            ("Warangal",         "20:45",  "20:50", "Day 1"),
            ("Vijayawada",       "23:00",  "23:15", "Day 1"),
            ("Gudur",            "02:10",  "02:12", "Day 2"),
            ("Nellore",          "02:55",  "02:57", "Day 2"),
            ("Chennai Central",  "07:15",  "Ends",  "Day 2"),
        ]
    },
    "3": {
        "name": "12841 Coromandel Express",
        "from": "Howrah Junction",
        "to": "Chennai Central",
        "duration": "26 hrs 30 mins",
        "stops": [
            ("Howrah Junction",  "Starts", "14:05", "Day 1"),
            ("Kharagpur",        "15:40",  "15:45", "Day 1"),
            ("Bhubaneswar",      "19:55",  "20:00", "Day 1"),
            ("Visakhapatnam",    "01:00",  "01:15", "Day 2"),
            ("Vijayawada",       "06:20",  "06:35", "Day 2"),
            ("Nellore",          "10:05",  "10:07", "Day 2"),
            ("Chennai Central",  "13:00",  "Ends",  "Day 2"),
        ]
    }
}

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
# FIX: Unified intent names used consistently throughout the handler
# -------------------------
def detect_intent(user_input):
    text = str(user_input).lower().strip()

    if text in ["1", "book", "ticket", "book ticket", "book a ticket", "general", "tatkal"]:
        return "book_ticket"

    # FIX: was "check_pnr" before, but handler checked "pnr_status"
    if text in ["2", "pnr", "pnr status", "check pnr"]:
        return "pnr_status"

    # FIX: was "cancel_ticket" before, but handler checked "cancel_ticket" — this one was fine,
    # kept consistent
    if text in ["3", "cancel", "cancel ticket"]:
        return "cancel_ticket"

    # FIX: was "train_schedule" before, handler also used "train_schedule" — was fine,
    # kept consistent
    if text in ["4", "schedule", "train schedule", "train"]:
        return "train_schedule"

    # FIX: was "check_seat" before, but handler checked "seat_availability"
    if text in ["5", "seat", "seat availability", "availability"]:
        return "seat_availability"

    if text in ["9", "agent", "customer care"]:
        return "agent"

    return None


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
        return {"prompt": "Session expired. Please start a new call.", "action": "hangup"}

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
            return {"prompt": "Enter Train Number to check schedule:\n1 - Karnataka Express (New Delhi to Bengaluru)\n2 - Charminar Express (Hyderabad to Chennai)\n3 - Coromandel Express (Howrah to Chennai)"}

        if intent == "seat_availability":
            session["stage"] = "availability_train"
            return {"prompt": "Enter Train Number to check seat availability."}

        if intent == "agent":
            session["stage"] = "customer_care"
            session["data"]["care_step"] = "menu"
            return {"prompt": (
                "Connecting to IRCTC Customer Care...\n"
                "Please hold while we connect you.\n\n"
                "You are now connected to IRCTC Support.\n"
                "Press 1 - Ticket related issue\n"
                "Press 2 - Refund status\n"
                "Press 3 - Complaint registration\n"
                "Press 4 - Talk to a live agent\n"
                "Press 0 - Go back to main menu"
            )}

        return {"prompt": f"Invalid input '{value}'. Please press 1-5 or 9."}

    # -------------------------
    # BOOKING FLOW
    # -------------------------
    if session["intent"] == "book_ticket":
        if stage == "source":
            if value not in STATIONS:
                return {"prompt": f"Invalid source '{value}'. Please enter a number 1-9.\n" +
                        "\n".join([f"{k}. {v}" for k, v in STATIONS.items()])}
            session["data"]["source"] = STATIONS[value]
            session["stage"] = "destination"
            return {"prompt": "Enter Destination Station:\n" + "\n".join([f"{k}. {v}" for k, v in STATIONS.items()])}

        if stage == "destination":
            if value not in STATIONS:
                return {"prompt": f"Invalid destination '{value}'. Please enter a number 1-9.\n" +
                        "\n".join([f"{k}. {v}" for k, v in STATIONS.items()])}
            if STATIONS[value] == session["data"]["source"]:
                return {"prompt": "Destination cannot be same as source. Please choose a different station."}
            session["data"]["destination"] = STATIONS[value]
            session["stage"] = "date"
            return {"prompt": "Select Journey Date:\n1. Today\n2. Tomorrow\n3. Day After Tomorrow"}

        if stage == "date":
            today = datetime.today()
            date_map = {"1": today, "2": today + timedelta(days=1), "3": today + timedelta(days=2)}
            if value not in date_map:
                return {"prompt": "Invalid option. Press 1 for Today, 2 for Tomorrow, 3 for Day After Tomorrow."}
            session["data"]["date"] = date_map[value].strftime("%Y-%m-%d")
            session["stage"] = "train_select"
            return {"prompt": "Available Trains:\n" + "\n".join(TRAINS) + "\nSelect train number (1-3)."}

        if stage == "train_select":
            try:
                idx = int(value) - 1
                if idx < 0 or idx >= len(TRAINS):
                    raise ValueError
                selected_train = TRAINS[idx]
            except (ValueError, IndexError):
                return {"prompt": f"Invalid selection. Please enter 1, 2, or 3.\n" + "\n".join(TRAINS)}
            del sessions[request.session_id]
            return {
                "prompt": f"Your ticket for {selected_train} from {session['data']['source']} to "
                          f"{session['data']['destination']} on {session['data']['date']} has been booked successfully.",
                "action": "hangup"
            }

    # -------------------------
    # PNR STATUS FLOW
    # FIX: was checking session["intent"] == "pnr_status" — now matches unified intent name
    # -------------------------
    if session["intent"] == "pnr_status" and stage == "pnr_number":
        # Accept any numeric input (relax strict 10-digit check for demo/testing)
        digits = "".join(filter(str.isdigit, value))
        if not digits:
            return {"prompt": "Invalid PNR. Please enter digits only. Try any number like 1234567890."}

        # Mock realistic responses based on last digit
        last = int(digits[-1])
        if last in [0, 1, 2, 3]:
            status = "CONFIRMED. Coach: S4, Seat: 32, Berth: Lower"
        elif last in [4, 5, 6]:
            status = "WAITING LIST - WL 12. Please check 4 hours before departure."
        elif last in [7, 8]:
            status = "RAC (Reservation Against Cancellation) - RAC 5. You will get a seat if someone cancels."
        else:
            status = "CONFIRMED. Coach: B2, Seat: 14, Berth: Upper"

        del sessions[request.session_id]
        return {"prompt": f"PNR {digits} Status: {status}", "action": "hangup"}

    # -------------------------
    # CANCEL TICKET FLOW
    # -------------------------
    if session["intent"] == "cancel_ticket" and stage == "cancel_train":
        del sessions[request.session_id]
        return {"prompt": f"Ticket for Train {value} has been successfully cancelled. Refund will be processed within 5-7 days.", "action": "hangup"}

    # -------------------------
    # TRAIN SCHEDULE FLOW
    # -------------------------
    if session["intent"] == "train_schedule":
        if stage == "schedule_train":
            if value not in TRAIN_SCHEDULES:
                return {"prompt": "Invalid train. Please select:\n1 - Karnataka Express\n2 - Charminar Express\n3 - Coromandel Express"}
            session["stage"] = "schedule_date"
            session["data"]["train"] = value
            t = TRAIN_SCHEDULES[value]
            return {"prompt": f"Train: {t['name']}\nFrom: {t['from']} → To: {t['to']}\nDuration: {t['duration']}\nEnter Journey Date (1=Today, 2=Tomorrow, 3=Day After):"}

        if stage == "schedule_date":
            train_key = session["data"]["train"]
            t = TRAIN_SCHEDULES[train_key]
            today = datetime.today()
            date_map = {"1": today, "2": today + timedelta(days=1), "3": today + timedelta(days=2)}
            journey_date = date_map.get(value, today).strftime("%d-%b-%Y")

            # Build stop-by-stop schedule
            lines = [f"Schedule for {t['name']} on {journey_date}:"]
            lines.append(f"{'Station':<22} {'Arr':>6}  {'Dep':>6}  {'Day'}")
            lines.append("-" * 46)
            for station, arr, dep, day in t["stops"]:
                lines.append(f"{station:<22} {arr:>6}  {dep:>6}  {day}")
            lines.append(f"\nTotal Duration: {t['duration']}")

            del sessions[request.session_id]
            return {"prompt": "\n".join(lines), "action": "hangup"}

    # -------------------------
    # SEAT AVAILABILITY FLOW
    # FIX: was checking session["intent"] == "seat_availability" — now matches unified intent name
    # -------------------------
    if session["intent"] == "seat_availability":
        if stage == "availability_train":
            session["data"]["train"] = value
            session["stage"] = "availability_date"
            return {"prompt": "Enter Journey Date (YYYY-MM-DD) to check seat availability."}

        if stage == "availability_date":
            train = session["data"]["train"]
            del sessions[request.session_id]
            return {"prompt": f"Seats for Train {train} on {value}: SL - Available, 3A - Waitlist 5, 2A - Available.", "action": "hangup"}

    # -------------------------
    # CUSTOMER CARE FLOW
    # -------------------------
    if session["intent"] == "agent" and stage == "customer_care":
        care_step = session["data"].get("care_step", "menu")

        if care_step == "menu":
            if value == "1":
                session["data"]["care_step"] = "ticket_issue"
                return {"prompt": (
                    "Ticket Related Issues:\n"
                    "Press 1 - Ticket not booked but amount deducted\n"
                    "Press 2 - Wrong name on ticket\n"
                    "Press 3 - Tatkal ticket issue\n"
                    "Press 4 - Duplicate booking\n"
                    "Press 0 - Go back"
                )}
            elif value == "2":
                session["data"]["care_step"] = "refund"
                return {"prompt": (
                    "Refund Status:\n"
                    "Your refund is processed within 5-7 working days after cancellation.\n"
                    "For UPI/Net Banking: 2-3 days\n"
                    "For Credit/Debit Card: 5-7 days\n"
                    "For IRCTC Wallet: Instant\n\n"
                    "Press 1 - Check refund status by PNR\n"
                    "Press 0 - Go back"
                )}
            elif value == "3":
                session["data"]["care_step"] = "complaint"
                return {"prompt": (
                    "Complaint Registration:\n"
                    "Please note your complaint will be registered.\n"
                    "IRCTC Helpline: 139\n"
                    "Email: care@irctc.co.in\n"
                    "Working Hours: 24x7\n\n"
                    "Press 1 - Register complaint about staff\n"
                    "Press 2 - Register complaint about food\n"
                    "Press 3 - Register complaint about cleanliness\n"
                    "Press 0 - Go back"
                )}
            elif value == "4":
                del sessions[request.session_id]
                return {"prompt": (
                    "Connecting you to a live IRCTC agent...\n"
                    "Estimated wait time: 3-5 minutes.\n"
                    "Alternatively call IRCTC helpline: 139\n"
                    "Thank you for contacting IRCTC. Goodbye!"
                ), "action": "hangup"}
            elif value == "0":
                session["stage"] = "main"
                session["intent"] = None
                session["data"] = {}
                return {"prompt": MAIN_MENU}
            else:
                return {"prompt": "Invalid option. Press 1-4 or 0 to go back."}

        elif care_step == "ticket_issue":
            responses = {
                "1": "Your complaint for amount deducted without booking has been noted.\nRefund will be processed in 3-5 working days.\nComplaint ID: TKT" + str(random.randint(100000,999999)),
                "2": "For name correction, visit nearest PRS counter with your ID proof.\nOnline name change is not permitted as per IRCTC policy.",
                "3": "Tatkal ticket issues are handled on priority.\nPlease call 139 with your PNR for immediate assistance.",
                "4": "Duplicate booking refund is auto-processed within 2 working days.\nCheck your registered email for confirmation.",
            }
            if value == "0":
                session["data"]["care_step"] = "menu"
                return {"prompt": (
                    "IRCTC Customer Care:\n"
                    "Press 1 - Ticket related issue\n"
                    "Press 2 - Refund status\n"
                    "Press 3 - Complaint registration\n"
                    "Press 4 - Talk to a live agent\n"
                    "Press 0 - Go back to main menu"
                )}
            msg = responses.get(value, "Invalid option.")
            del sessions[request.session_id]
            return {"prompt": msg + "\n\nThank you for contacting IRCTC!", "action": "hangup"}

        elif care_step == "refund":
            if value == "1":
                del sessions[request.session_id]
                return {"prompt": "Please enter your PNR to check refund. For now showing mock status:\nPNR refund of Rs.450 processed on 10-Mar-2026.\nThank you!", "action": "hangup"}
            elif value == "0":
                session["data"]["care_step"] = "menu"
                return {"prompt": (
                    "IRCTC Customer Care:\n"
                    "Press 1 - Ticket related issue\n"
                    "Press 2 - Refund status\n"
                    "Press 3 - Complaint registration\n"
                    "Press 4 - Talk to a live agent\n"
                    "Press 0 - Go back to main menu"
                )}
            return {"prompt": "Invalid option. Press 1 or 0."}

        elif care_step == "complaint":
            complaint_types = {
                "1": "staff behaviour",
                "2": "food quality",
                "3": "cleanliness"
            }
            if value == "0":
                session["data"]["care_step"] = "menu"
                return {"prompt": (
                    "IRCTC Customer Care:\n"
                    "Press 1 - Ticket related issue\n"
                    "Press 2 - Refund status\n"
                    "Press 3 - Complaint registration\n"
                    "Press 4 - Talk to a live agent\n"
                    "Press 0 - Go back to main menu"
                )}
            ctype = complaint_types.get(value)
            if ctype:
                complaint_id = "CMP" + str(random.randint(100000, 999999))
                del sessions[request.session_id]
                return {"prompt": f"Your complaint about {ctype} has been registered.\nComplaint ID: {complaint_id}\nYou will receive an update within 48 hours on your registered mobile.\nThank you!", "action": "hangup"}
            return {"prompt": "Invalid option. Press 1, 2, 3 or 0."}

    return {"prompt": "Something went wrong. Please start a new call.", "action": "hangup"}