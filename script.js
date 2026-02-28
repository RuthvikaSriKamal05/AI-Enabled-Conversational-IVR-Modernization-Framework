const API_URL = "http://localhost:8000";

let sessionId = null;
let currentMenu = null;
let callActive = false;
let isInputMode = false;
let inputBuffer = "";

const display = document.getElementById("display");

// Display messages
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
// SEND TO BACKEND
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

        // Only end call if backend says so
        if (data.action === "hangup") {
            addMessage(data.message);
            endCall();
            return;
        }

        currentMenu = data.menu;

        // Detect input states
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

        // If in input mode → buffer digits
        if (isInputMode) {

            inputBuffer += digit;
            addMessage("Entered: " + inputBuffer);

        } else {

            // Normal navigation
            sendToBackend(digit);
        }
    });
});


// =======================
// SUBMIT BUTTON (IMPORTANT)
// =======================
document.getElementById("submitInput").addEventListener("click", function () {

    if (!callActive || !isInputMode || inputBuffer === "") return;

    sendToBackend(inputBuffer);

    inputBuffer = "";
    isInputMode = false;
});


// =======================
// HANGUP
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