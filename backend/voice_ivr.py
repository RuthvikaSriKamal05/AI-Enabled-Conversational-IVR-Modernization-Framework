import speech_recognition as sr
import requests

API_URL = "http://localhost:8000"

# -------------------------
# SPEECH TO TEXT
# -------------------------
def listen_voice():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Listening...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=4)

    try:
        text = recognizer.recognize_google(audio)
        print("You said:", text)
        return text.lower()
    except:
        print("❌ Could not understand voice")
        return ""

# -------------------------
# MAP TEXT TO DIGIT
# -------------------------
def map_text_to_digit(text):
    if any(word in text for word in ["book", "ticket", "general", "tatkal"]):
        return "1"
    if "pnr" in text:
        return "2"
    if "cancel" in text:
        return "3"
    if any(word in text for word in ["schedule", "train"]):
        return "4"
    if any(word in text for word in ["seat", "availability"]):
        return "5"
    if any(word in text for word in ["agent", "customer care"]):
        return "9"
    if text in ["1","2","3","4"]:
        return text
    return None

# -------------------------
# START CALL
# -------------------------
def start_call():
    response = requests.post(f"{API_URL}/ivr/start", json={"caller_number": "9999999999"})
    data = response.json()
    print("\n📞 Call Started")
    print(data["prompt"])
    return data["session_id"]

# -------------------------
# SEND INPUT
# -------------------------
def send_input(session_id, digit):
    response = requests.post(f"{API_URL}/ivr/input", json={"session_id": session_id, "value": digit, "isDigit": True})
    data = response.json()
    print("\n" + data["prompt"])
    return data

# -------------------------
# MAIN LOOP
# -------------------------
def run_voice_ivr():
    session_id = start_call()

    while True:
        text = listen_voice()
        if not text:
            continue

        digit = map_text_to_digit(text)
        if not digit:
            print("❌ Could not detect intent. Try again...")
            continue

        resp = send_input(session_id, digit)
        if "successfully" in resp.get("prompt",""):
            print("✅ Booking completed!")
            break

if __name__ == "__main__":
    run_voice_ivr()