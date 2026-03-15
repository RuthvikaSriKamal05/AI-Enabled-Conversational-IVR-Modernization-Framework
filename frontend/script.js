const API_URL = "http://127.0.0.1:8000";

let sessionId = null;
let callActive = false;
let conversationState = 0;
let inputBuffer = "";
let isInputMode = false;

const display = document.getElementById("display");

// =======================
// DISPLAY + TTS
// =======================
function addMessage(text, type = "system", speak = true) {
    const p = document.createElement("p");
    p.innerHTML = text.replace(/\n/g, "<br>");
    p.className = type === "system" ? "system-msg" : "user-msg";
    display.appendChild(p);
    display.scrollTop = display.scrollHeight;
    if (speak && type === "system") speakText(text);
}

function speakText(text, voiceName = "Google UK English Female") {
    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    utterance.voice = voices.find(v => v.name === voiceName) || voices[0];
    utterance.rate = 1;
    utterance.pitch = 1;
    window.speechSynthesis.speak(utterance);
}

// =======================
// START CALL
// =======================
document.getElementById("startCall").addEventListener("click", async () => {
    if (callActive) return;
    try {
        const res = await fetch(`${API_URL}/ivr/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ caller_number: "WebSimulator" })
        });
        const data = await res.json();
        sessionId = data.session_id;
        callActive = true;
        conversationState = 0;
        addMessage("📞 Call Started");
        addMessage("Hello! How can I help you today?");
    } catch {
        addMessage("⚠️ Backend not running.", "system", false);
    }
});

// =======================
// SEND INPUT (Unified for text, voice, digit)
// =======================
async function handleInput(value, isDigit = false) {
    if (!callActive) return;
    try {
        const res = await fetch(`${API_URL}/ivr/input`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, value, state: conversationState, isDigit })
        });
        const data = await res.json();
        if (data.error) return addMessage(data.error, "system", false);

        addMessage(data.reply);
        conversationState = data.nextState || conversationState;

        if (data.action === "hangup") endCall();
    } catch {
        addMessage("⚠️ Server error.", "system", false);
    }
}

// =======================
// INPUT HANDLERS
// =======================

// Keypad
document.querySelectorAll(".key").forEach(btn =>
    btn.addEventListener("click", () => {
        if (!callActive) return;
        const digit = btn.getAttribute("data-digit");
        addMessage(`You pressed: ${digit}`, "user", false);
        if (isInputMode) {
            inputBuffer += digit;
            addMessage("Entered: " + inputBuffer, "user", false);
        } else handleInput(digit, true);
    })
);

// Submit keypad
document.getElementById("submitInput").addEventListener("click", () => {
    if (!callActive || !isInputMode || inputBuffer === "") return;
    handleInput(inputBuffer, true);
    inputBuffer = "";
    isInputMode = false;
});

// Text input
document.getElementById("sendText").addEventListener("click", () => {
    if (!callActive) return addMessage("Start call first.", "system", false);
    const text = document.getElementById("userText").value.trim();
    if (!text) return;
    addMessage("You: " + text, "user", false);
    const intent = detectIntent(text);
    if (intent === "unknown") addMessage("❓ Sorry, I didn't understand. Try: Book ticket, Check PNR, Cancel ticket.", "system", false);
    else handleInput(intent);
    document.getElementById("userText").value = "";
});

// Voice input
document.getElementById("voiceInput").addEventListener("click", () => {
    if (!callActive) return addMessage("Start call first.", "system", false);
    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    addMessage("🎤 Listening...", "system", false);

    recognition.onresult = (event) => {
        const text = event.results[0][0].transcript;
        addMessage("You said: " + text, "user", false);
        const intent = detectIntent(text);
        if (intent === "unknown") addMessage("❓ Could not understand command.", "system", false);
        else handleInput(intent);
    };
    recognition.onerror = () => addMessage("⚠️ Voice recognition error.", "system", false);
    recognition.start();
});

// =======================
// INTENT DETECTION (optimized)
// =======================
const intentMap = {
    book: "book_ticket",
    pnr: "check_pnr",
    status: "check_pnr",
    cancel: "cancel_ticket",
    schedule: "train_schedule",
    seat: "check_seat",
    availability: "check_seat",
    general: "general_ticket",
    tatkal: "tatkal_ticket",
    hyderabad: "1",
    chennai: "2",
    delhi: "3",
    mumbai: "4",
    howrah: "5",
    bengaluru: "6",
    bangalore: "6",
    secunderabad: "7",
    vijayawada: "8",
    ahmedabad: "9",
    today: "today",
    tomorrow: "tomorrow",
    "day after": "day_after"
};

function detectIntent(text) {
    text = text.toLowerCase();
    for (const key in intentMap) if (text.includes(key)) return intentMap[key];
    return "unknown";
}

// =======================
// END CALL
// =======================
function endCall() {
    callActive = false;
    sessionId = null;
    inputBuffer = "";
    isInputMode = false;
    conversationState = 0;
    addMessage("--- Call Ended ---");
}

document.getElementById("hangupCall").addEventListener("click", () => { if (callActive) endCall(); });