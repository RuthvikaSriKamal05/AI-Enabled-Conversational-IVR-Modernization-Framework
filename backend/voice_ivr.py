import speech_recognition as sr
import requests

API_URL = "http://localhost:8000"
MAX_RETRIES = 3   # how many times to re-listen before giving up on one step

# -------------------------
# TTS — optional, falls back gracefully
# -------------------------
try:
    import pyttsx3
    _tts = pyttsx3.init()
    _tts.setProperty("rate", 150)
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

def speak(text):
    print(f"\n[IVR] {text}")
    if TTS_AVAILABLE:
        _tts.say(text)
        _tts.runAndWait()

# -------------------------
# LISTEN — returns top N transcripts (not just the best one)
# Using show_all=True + best-of-N gives much better accuracy
# -------------------------
def listen(timeout=7, phrase_limit=6, n_best=5):
    """
    Returns a list of candidate transcripts ordered by confidence.
    Uses Google's alternative results when available.
    Falls back to single result if alternatives aren't returned.
    """
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300        # lower = more sensitive
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8         # shorter pause = faster response

    with sr.Microphone() as source:
        print("🎤 Listening…")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        except sr.WaitTimeoutError:
            print("   [Timeout] No speech detected.")
            return []

    try:
        # show_all=True returns a dict with "alternative" list from Google
        raw = recognizer.recognize_google(audio, show_all=True)
        if not raw or "alternative" not in raw:
            return []
        alternatives = [a["transcript"].strip().lower() for a in raw["alternative"][:n_best]]
        print(f"   Heard (top {len(alternatives)}): {alternatives}")
        return alternatives
    except sr.UnknownValueError:
        print("   [Error] Could not understand audio.")
        return []
    except sr.RequestError as e:
        print(f"   [Error] Speech service error: {e}")
        return []

# -------------------------
# SMART MAPPER
# Maps a list of speech alternatives → backend value
# based on the current prompt text
# -------------------------
def smart_map(alternatives, prompt):
    """
    Tries each alternative in order. Returns first successful mapping.
    """
    prompt = prompt.lower()

    for text in alternatives:
        text = text.strip().lower()

        if "press 1" in prompt or "welcome" in prompt:
            r = _map_main_menu(text)
        elif "source station" in prompt or "destination station" in prompt:
            r = _map_station(text)
        elif "journey date" in prompt and "yyyy" not in prompt:
            r = _map_date(text)
        elif "available trains" in prompt or "select train" in prompt:
            r = _map_train_select(text)
        elif "pnr number" in prompt:
            r = _extract_digits(text)
        elif "train number" in prompt:
            r = _extract_digits(text) or text
        elif "yyyy" in prompt:
            r = _parse_spoken_date(text)
        else:
            r = _extract_digits(text) or text

        if r:
            return r, text   # return (mapped_value, original_transcript)

    return None, alternatives[0] if alternatives else ""

def _map_main_menu(text):
    rules = [
        ("1", ["1","one","book","ticket","booking","general","tatkal","reserve","reservation"]),
        ("2", ["2","two","pnr","status","check pnr","pnr status"]),
        ("3", ["3","three","cancel","cancellation"]),
        ("4", ["4","four","schedule","timetable","timing","timings","train schedule"]),
        ("5", ["5","five","seat","seats","availability","available","seat availability"]),
        ("9", ["9","nine","agent","customer","care","help","operator","human"]),
    ]
    for digit, words in rules:
        if any(w in text for w in words):
            return digit
    return None

def _map_station(text):
    map_ = {
        "1": ["hyderabad","deccan","hyd","hidrabad"],
        "2": ["chennai","madras","central","chenai"],
        "3": ["delhi","new delhi","ndls","dilli"],
        "4": ["mumbai","bombay","csmt","victoria","mumbi"],
        "5": ["howrah","kolkata","calcutta","kolkatta"],
        "6": ["bengaluru","bangalore","bengalore","blr"],
        "7": ["secunderabad","secundrabad","secunder"],
        "8": ["vijayawada","bezawada","vijawada","vijaya"],
        "9": ["ahmedabad","amdavad","ahmed","ahemdabad"],
    }
    for digit, keywords in map_.items():
        if any(k in text for k in keywords):
            return digit
    spoken = {"one":"1","two":"2","three":"3","four":"4","five":"5",
              "six":"6","seven":"7","eight":"8","nine":"9"}
    for word, digit in spoken.items():
        if word in text:
            return digit
    return _extract_digits(text)

def _map_date(text):
    if any(w in text for w in ["today","one","1"]):       return "1"
    if any(w in text for w in ["tomorrow","two","2"]):    return "2"
    if any(w in text for w in ["day after","three","3"]): return "3"
    return _extract_digits(text)

def _map_train_select(text):
    if any(w in text for w in ["one","first","karnataka","1"]):   return "1"
    if any(w in text for w in ["two","second","charminar","2"]):  return "2"
    if any(w in text for w in ["three","third","coromandel","3"]): return "3"
    return _extract_digits(text)

def _extract_digits(text):
    d = "".join(filter(str.isdigit, text))
    return d or None

def _parse_spoken_date(text):
    digits = "".join(filter(str.isdigit, text))
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    import re
    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return m.group(0) if m else text

# -------------------------
# API CALLS
# -------------------------
def start_call():
    try:
        resp = requests.post(f"{API_URL}/ivr/start", json={"caller_number": "9999999999"})
        data = resp.json()
        speak(data["prompt"])
        return data["session_id"], data["prompt"]
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend. Is FastAPI running on port 8000?")
        raise SystemExit(1)

def send_input(session_id, value):
    resp = requests.post(f"{API_URL}/ivr/input",
                         json={"session_id": session_id, "value": value})
    data = resp.json()
    speak(data.get("prompt", ""))
    return data

# -------------------------
# MAIN LOOP
# -------------------------
def run():
    print("=" * 40)
    print("  IRCTC Voice IVR — Python Client")
    print("=" * 40)
    session_id, current_prompt = start_call()

    while True:
        retries = 0
        mapped = None
        heard = ""

        # Keep listening until we get a valid mapped value (or hit retry limit)
        while retries < MAX_RETRIES:
            alternatives = listen()

            if not alternatives:
                retries += 1
                speak(f"I didn't catch that. Please try again. Attempt {retries} of {MAX_RETRIES}.")
                continue

            mapped, heard = smart_map(alternatives, current_prompt)

            if mapped:
                print(f"   ✅ Mapped '{heard}' → '{mapped}'")
                break
            else:
                retries += 1
                speak(f"Sorry, I heard '{heard}' but couldn't match it. Please try again.")

        # If still no match after retries, ask for manual input
        if not mapped:
            print(f"\n⚠️  Could not understand after {MAX_RETRIES} attempts.")
            manual = input("   Type your input manually (or press Enter to skip): ").strip()
            if not manual:
                speak("Ending session due to repeated unrecognised input.")
                break
            mapped = manual

        # Send to backend
        resp = send_input(session_id, mapped)
        current_prompt = resp.get("prompt", "")

        if resp.get("action") == "hangup":
            print("\n✅ Session ended.")
            break

if __name__ == "__main__":
    run()