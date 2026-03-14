import speech_recognition as sr
import requests

# Backend URL
API_URL = "http://localhost:8000"

# -------------------------
# SPEECH TO TEXT
# -------------------------
def listen_voice():

    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("🎤 Adjusting noise...")
        recognizer.adjust_for_ambient_noise(source, duration=1)

        print("🎤 Speak your request...")
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=4)

    try:
        text = recognizer.recognize_google(audio)
        print("You said:", text)
        return text.lower()

    except:
        print("Could not understand voice")
        return ""


# -------------------------
# INTENT DETECTION
# -------------------------
def detect_intent(text):

    if "1" in text or "one" in text or "book" in text or "ticket" in text or "general" in text or "tatkal" in text:
        return "1"

    if "2" in text or "two" in text or "pnr" in text:
        return "2"

    if "3" in text or "three" in text or "cancel" in text:
        return "3"

    if "4" in text or "four" in text or "schedule" in text or "train" in text:
        return "4"

    if "5" in text or "five" in text or "seat" in text or "availability" in text:
        return "5"

    if "9" in text or "nine" in text or "customer care" in text or "agent" in text:
        return "9"

    return None


# -------------------------
# START IVR CALL
# -------------------------
def start_call():

    response = requests.post(
        f"{API_URL}/ivr/start",
        json={"caller_number": "9999999999"}
    )

    data = response.json()

    print("\n📞 Call Started")
    print(data["prompt"])

    return data["session_id"]


# -------------------------
# SEND INPUT
# -------------------------
def send_digit(session_id, user_input):

    response = requests.post(
        f"{API_URL}/ivr/input",
        json={
            "session_id": session_id,
            "digit": user_input
        }
    )

    data = response.json()

    if "prompt" in data:
        print("\n", data["prompt"])

    if "message" in data:
        print("\n", data["message"])

# -------------------------
# MAIN PROGRAM
# -------------------------
def run_voice_ivr():

    session_id = start_call()

    first_menu = True

    while True:

        text = listen_voice()

        if first_menu:
            digit = detect_intent(text)

            if digit is None:
                print("Try again...")
                continue

            send_digit(session_id, digit)
            first_menu = False

        else:
            # send voice text directly to backend
            send_digit(session_id, text)
# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    run_voice_ivr()