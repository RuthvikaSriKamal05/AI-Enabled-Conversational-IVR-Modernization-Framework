const API_URL = "http://127.0.0.1:8000";

let sessionId = null;
let callActive = false;
let inputBuffer = "";
let isBufferingMode = false;
let currentPrompt = "";
let isSpeaking = false;  // track TTS state

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

// Returns a Promise that resolves when TTS finishes speaking
function speakText(text) {
    return new Promise((resolve) => {
        window.speechSynthesis.cancel();
        isSpeaking = true;

        const utterance = new SpeechSynthesisUtterance(text);
        const voices = window.speechSynthesis.getVoices();
        utterance.voice =
            voices.find(v => v.name === "Google UK English Female") ||
            voices.find(v => v.lang === "en-IN") ||
            voices.find(v => v.lang.startsWith("en")) ||
            voices[0];
        utterance.rate = 0.95;
        utterance.pitch = 1;

        utterance.onend = () => {
            isSpeaking = false;
            resolve();
        };
        utterance.onerror = () => {
            isSpeaking = false;
            resolve();  // resolve anyway so mic still opens
        };

        window.speechSynthesis.speak(utterance);
    });
}

// Wait until TTS is done, then run callback
function waitForSpeechThenDo(fn) {
    if (!isSpeaking) {
        fn();
    } else {
        // Poll every 100ms until speaking stops
        const interval = setInterval(() => {
            if (!isSpeaking) {
                clearInterval(interval);
                fn();
            }
        }, 100);
    }
}

// =======================
// SMART INTENT MAPPER
// =======================
function smartMap(text, prompt) {
    text = text.toLowerCase().trim();
    prompt = (prompt || "").toLowerCase();

    if (prompt.includes("press 1") || prompt.includes("welcome"))
        return mapMainMenu(text);
    if (prompt.includes("source station") || prompt.includes("destination station"))
        return mapStation(text);
    if (prompt.includes("journey date") && !prompt.includes("yyyy"))
        return mapDate(text);
    if (prompt.includes("available trains") || prompt.includes("select train"))
        return mapTrainSelect(text);
    if (prompt.includes("pnr number"))   return extractDigits(text);
    if (prompt.includes("train number")) return extractDigits(text) || text;
    if (prompt.includes("yyyy"))         return parseSpokenDate(text);

    return extractDigits(text) || text;
}

function mapMainMenu(text) {
    // Check PHRASES first so "cancel ticket" doesnt match "ticket" -> book
    const phrases = [
        { digit: "3", list: ["cancel ticket","cancel my ticket","cancellation"] },
        { digit: "1", list: ["book ticket","book a ticket","ticket booking","tatkal ticket","general ticket"] },
        { digit: "2", list: ["pnr status","check pnr","pnr check"] },
        { digit: "4", list: ["train schedule","train timing","check schedule"] },
        { digit: "5", list: ["seat availability","check seat","available seats"] },
        { digit: "9", list: ["customer care","talk to agent"] },
    ];
    for (const { digit, list } of phrases) {
        if (list.some(p => text.includes(p))) return digit;
    }
    // Single word fallback
    const single = [
        { digit: "1", list: ["1","one","book","booking","general","tatkal","reserve"] },
        { digit: "2", list: ["2","two","pnr","status"] },
        { digit: "3", list: ["3","three","cancel"] },
        { digit: "4", list: ["4","four","schedule","timetable","timing"] },
        { digit: "5", list: ["5","five","seat","seats","availability","available"] },
        { digit: "9", list: ["9","nine","agent","customer","care","help","operator"] },
    ];
    for (const { digit, list } of single) {
        if (list.some(w => text.includes(w))) return digit;
    }
    return null;
}

function mapStation(text) {
    const map = {
        "1": ["hyderabad","deccan","hyd","hidrabad"],
        "2": ["chennai","madras","central","chenai"],
        "3": ["delhi","new delhi","ndls","dilli"],
        "4": ["mumbai","bombay","csmt","victoria","mumbi"],
        "5": ["howrah","kolkata","calcutta","kolkatta"],
        "6": ["bengaluru","bangalore","bengalore","blr"],
        "7": ["secunderabad","secundrabad","secunder"],
        "8": ["vijayawada","bezawada","vijawada","vijaya"],
        "9": ["ahmedabad","amdavad","ahmed","ahemdabad"]
    };
    for (const [digit, keywords] of Object.entries(map)) {
        if (keywords.some(k => text.includes(k))) return digit;
    }
    const spoken = { "one":"1","two":"2","three":"3","four":"4","five":"5",
                     "six":"6","seven":"7","eight":"8","nine":"9" };
    for (const [word, digit] of Object.entries(spoken)) {
        if (text.includes(word)) return digit;
    }
    return extractDigits(text);
}

function mapDate(text) {
    if (text.match(/\btoday\b|\bone\b|^1$/))                    return "1";
    if (text.match(/\btomorrow\b|\btwo\b|^2$/))                 return "2";
    if (text.match(/day after|after tomorrow|\bthree\b|^3$/))   return "3";
    return extractDigits(text);
}

function mapTrainSelect(text) {
    if (text.match(/\bone\b|\bfirst\b|karnataka|^1$/))    return "1";
    if (text.match(/\btwo\b|\bsecond\b|charminar|^2$/))   return "2";
    if (text.match(/\bthree\b|\bthird\b|coromandel|^3$/)) return "3";
    return extractDigits(text);
}

function extractDigits(text) {
    const d = text.replace(/\D/g, "");
    return d || null;
}

function parseSpokenDate(text) {
    const digits = text.replace(/\D/g, "");
    if (digits.length === 8) return `${digits.slice(0,4)}-${digits.slice(4,6)}-${digits.slice(6,8)}`;
    const match = text.match(/\d{4}-\d{2}-\d{2}/);
    return match ? match[0] : text;
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
        inputBuffer = "";
        isBufferingMode = false;
        display.innerHTML = "";
        currentPrompt = data.prompt;
        addMessage("📞 Call Started");
        addMessage(data.prompt);
    } catch {
        addMessage("⚠️ Backend not running. Start the FastAPI server first.", "system", false);
    }
});

// =======================
// CORE INPUT HANDLER
// =======================
async function handleInput(value) {
    if (!callActive) return;
    addMessage("You: " + value, "user", false);

    try {
        const res = await fetch(`${API_URL}/ivr/input`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, value })
        });
        const data = await res.json();
        if (data.error) {
            addMessage("⚠️ " + data.error, "system", false);
            return;
        }
        currentPrompt = data.prompt;
        addMessage(data.prompt);
        // Auto-enable buffer mode for multi-digit inputs
        const pl = data.prompt.toLowerCase();
        if (pl.includes("pnr number") || pl.includes("train number")) {
            isBufferingMode = true;
            inputBuffer = "";
            addMessage("💡 Type it in the text box and press Send, or use keypad + Submit.", "system", false);
        } else {
            isBufferingMode = false;
            inputBuffer = "";
        }
        if (data.action === "hangup") endCall(false);
    } catch {
        addMessage("⚠️ Server error. Is the backend running?", "system", false);
    }
}

// =======================
// KEYPAD
// =======================
document.querySelectorAll(".key").forEach(btn =>
    btn.addEventListener("click", () => {
        if (!callActive) return;
        const digit = btn.getAttribute("data-digit");
        if (isBufferingMode) {
            inputBuffer += digit;
            addMessage("Entered so far: " + inputBuffer, "user", false);
        } else {
            handleInput(digit);
        }
    })
);

document.getElementById("submitInput").addEventListener("click", () => {
    if (!callActive || inputBuffer === "") return;
    handleInput(inputBuffer);
    inputBuffer = "";
    isBufferingMode = false;
});

// =======================
// TEXT INPUT
// =======================
document.getElementById("sendText").addEventListener("click", sendTextInput);
document.getElementById("userText").addEventListener("keydown", e => {
    if (e.key === "Enter") sendTextInput();
});

function sendTextInput() {
    if (!callActive) return addMessage("Please start a call first.", "system", false);
    const text = document.getElementById("userText").value.trim();
    if (!text) return;
    document.getElementById("userText").value = "";
    handleInput(text);
}

// =======================
// VOICE INPUT
// KEY FIX: Wait for TTS to fully finish before opening microphone.
// The "aborted" error was caused by the mic starting while the IVR
// was still speaking — browser kills recognition immediately in that case.
// =======================
document.getElementById("voiceInput").addEventListener("click", () => {
    if (!callActive) return addMessage("Please start a call first.", "system", false);

    // Stop any ongoing TTS first
    window.speechSynthesis.cancel();
    isSpeaking = false;

    // Wait 700ms for browser audio pipeline to fully release mic before opening recognition
    // This is the key fix for "aborted" errors — mic and speaker can't be open simultaneously
    addMessage("⏳ Starting mic…", "system", false);
    setTimeout(() => startVoiceInput(), 700);
});

function startVoiceInput(retryCount = 0) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition)
        return addMessage("⚠️ Voice not supported. Use Chrome or Edge.", "system", false);

    const recognition = new SpeechRecognition();
    recognition.lang = "en-IN";          // Indian English — better accent accuracy
    recognition.interimResults = false;
    recognition.maxAlternatives = 5;     // try all 5 browser guesses before giving up

    addMessage("🎤 Listening… speak now", "system", false);

    recognition.onresult = (event) => {
        const alternatives = Array.from(event.results[0]).map(r => r.transcript.trim());
        const best = alternatives[0];

        const altText = alternatives.length > 1
            ? `<br><small style="color:#aaa">Also heard: ${alternatives.slice(1).join(" | ")}</small>`
            : "";
        addMessage(`🔊 Heard: "<b>${best}</b>"${altText}`, "user", false);

        let mapped = null;
        for (const alt of alternatives) {
            mapped = smartMap(alt, currentPrompt);
            if (mapped) break;
        }

        if (mapped) {
            addMessage(`✅ Matched: <b>${mapped}</b>`, "system", false);
            handleInput(mapped);
        } else {
            const btnStyle = "margin:4px;padding:5px 12px;border:none;border-radius:8px;color:white;cursor:pointer;font-size:13px";
            addMessage(
                `❓ Couldn't match "<b>${best}</b>".<br>` +
                `<button onclick="handleInput('${best.replace(/'/g,"\\'")}');this.closest('p').remove()" ` +
                    `style="${btnStyle};background:#00c853">Send as-is</button>` +
                `<button onclick="startVoiceInput();this.closest('p').remove()" ` +
                    `style="${btnStyle};background:#ff9800">🎤 Try again</button>`,
                "system", false
            );
        }
    };

    recognition.onerror = (e) => {
        console.warn("Speech recognition error:", e.error);

        if (e.error === "aborted") {
            // aborted = mic conflict with audio playback, wait a bit more and retry
            if (retryCount < 2) {
                addMessage("⏳ Audio conflict detected, retrying in 1s…", "system", false);
                setTimeout(() => startVoiceInput(retryCount + 1), 1000);
            } else {
                addMessage("⚠️ Mic couldn't start. Make sure nothing else is playing audio, then try again.", "system", false);
            }
            return;
        }

        if ((e.error === "no-speech") && retryCount < 2) {
            addMessage(`⚠️ No speech heard. Retrying… (${retryCount + 1}/2)`, "system", false);
            setTimeout(() => startVoiceInput(retryCount + 1), 600);
            return;
        }

        addMessage(`⚠️ Voice error (${e.error}). Try the keypad or text input.`, "system", false);
    };

    recognition.start();
}

// =======================
// END CALL
// =======================
function endCall(announce = true) {
    callActive = false;
    sessionId = null;
    inputBuffer = "";
    isBufferingMode = false;
    currentPrompt = "";
    isSpeaking = false;
    window.speechSynthesis.cancel();
    if (announce) addMessage("--- Call Ended ---");
}

document.getElementById("hangupCall").addEventListener("click", () => {
    if (callActive) endCall(true);
});