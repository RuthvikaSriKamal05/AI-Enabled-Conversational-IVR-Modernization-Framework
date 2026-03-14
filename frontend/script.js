const API_URL = "http://127.0.0.1:8000";

let sessionId = null;
let currentMenu = null;
let callActive = false;
let isInputMode = false;
let inputBuffer = "";

const display = document.getElementById("display");


// =======================
// DISPLAY MESSAGES
// =======================
function addMessage(text, type = "system") {

    const p = document.createElement("p");

    p.innerHTML = text.replace(/\n/g, "<br>");
    p.className = type === "system" ? "system-msg" : "user-msg";

    display.appendChild(p);
    display.scrollTop = display.scrollHeight;
}



// =======================
// START CALL
// =======================
document.getElementById("startCall").addEventListener("click", async () => {

    if (callActive) return;

    try {

        const response = await fetch(`${API_URL}/ivr/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ caller_number: "WebSimulator" })
        });

        const data = await response.json();

        sessionId = data.session_id;
        currentMenu = data.menu;
        callActive = true;

        addMessage("📞 Call Started");
        addMessage(data.prompt);

    } catch (err) {

        addMessage("⚠️ Backend not running.");
    }
});



// =======================
// SEND INPUT TO BACKEND
// =======================
async function sendToBackend(value) {

    try {

        const response = await fetch(`${API_URL}/ivr/input`, {

            method: "POST",

            headers: { "Content-Type": "application/json" },

            body: JSON.stringify({
                session_id: sessionId,
                digit: value
            })
        });

        const data = await response.json();

        console.log(data);

        if (data.error) {
            addMessage(data.error);
            return;
        }

        if (data.action === "hangup") {
            addMessage(data.message);
            endCall();
            return;
        }

        currentMenu = data.menu;

        if (["pnr", "cancel", "schedule",
            "availability_train",
            "availability_date",
            "general_date"].includes(currentMenu)) {

            isInputMode = true;
            inputBuffer = "";

        } else {

            isInputMode = false;
        }

        addMessage(data.prompt);

    } catch (error) {

        addMessage("⚠️ Server error.");
        console.error(error);
    }
}



// =======================
// KEYPAD LOGIC
// =======================
document.querySelectorAll(".key").forEach(button => {

    button.addEventListener("click", function () {

        if (!callActive) return;

        const digit = this.getAttribute("data-digit");

        addMessage(`You pressed: ${digit}`, "user");

        if (isInputMode) {

            inputBuffer += digit;
            addMessage("Entered: " + inputBuffer);

        } else {

            sendToBackend(digit);
        }
    });
});



// =======================
// SUBMIT KEYPAD INPUT
// =======================
document.getElementById("submitInput").addEventListener("click", function () {

    if (!callActive || !isInputMode || inputBuffer === "") return;

    sendToBackend(inputBuffer);

    inputBuffer = "";
    isInputMode = false;
});



// =======================
// MILESTONE 3 FEATURE
// CONVERSATIONAL TEXT INPUT
// =======================

document.getElementById("sendText").addEventListener("click", function () {

    if (!callActive) {
        addMessage("Start call first.");
        return;
    }

    const inputBox = document.getElementById("userText");
    const text = inputBox.value.trim();

    if (text === "") return;

    addMessage("You: " + text, "user");

    const intent = detectIntent(text);

    if (intent === "unknown") {

        addMessage("❓ Sorry, I didn't understand. Try saying: Book ticket, Check PNR, Cancel ticket.");

    } else {

        sendToBackend(intent);
    }

    inputBox.value = "";
});



// =======================
// INTENT DETECTION
// =======================
function detectIntent(text) {

    text = text.toLowerCase();

    if (text.includes("book"))
        return "1";

    if (text.includes("pnr") || text.includes("status"))
        return "2";

    if (text.includes("cancel"))
        return "3";

    if (text.includes("schedule"))
        return "4";

    if (text.includes("seat") || text.includes("availability"))
        return "5";

    return "unknown";
}



// =======================
// END CALL
// =======================
function endCall() {

    callActive = false;
    sessionId = null;
    currentMenu = null;
    isInputMode = false;
    inputBuffer = "";

    addMessage("--- Call Ended ---");
}



document.getElementById("hangupCall").addEventListener("click", () => {

    if (callActive) endCall();
});
