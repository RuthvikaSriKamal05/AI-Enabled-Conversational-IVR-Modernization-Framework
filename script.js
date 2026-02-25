const API_URL = "http://localhost:8000";

// Keeping track of the call state so we don't try to press buttons while hung up
let sessionId = null;
let currentMenu = null;
let callActive = false;

const display = document.getElementById("display");

// Just a quick way to shove text onto the screen and keep it scrolled down
function addMessage(text, type = "system") {
    const p = document.createElement("p");
    p.textContent = text;
    p.className = type === "system" ? "system-msg" : "user-msg";
    display.appendChild(p);
    
    // Auto-scroll so the user doesn't have to manually chase the convo
    display.scrollTop = display.scrollHeight;
}

// Dialing in
document.getElementById("startCall").addEventListener("click", async () => {
    if (callActive) return; // Don't start a second call if one is already going

    try {
        const response = await fetch(`${API_URL}/ivr/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ caller_number: "WebSimulator" })
        });

        const data = await response.json();

        // Save the session details we get back from the server
        sessionId = data.session_id;
        currentMenu = data.menu;
        callActive = true;

        addMessage("📞 Call Started");
        addMessage(data.prompt);
    } catch (err) {
        addMessage("⚠️ Server isn't responding. Is the backend running?");
    }
});

// Keypad logic
document.querySelectorAll(".key").forEach(button => {
    button.addEventListener("click", async function () {
        if (!callActive) return; // Ignore clicks if there's no active call

        const digit = this.getAttribute("data-digit");
        addMessage(`You pressed: ${digit}`, "user");

        // Tell the server which button was pressed and wait for the "voice" response
        const response = await fetch(`${API_URL}/ivr/input`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sessionId,
                digit: digit,
                current_menu: currentMenu
            })
        });

        const data = await response.json();

        // If the server says "hangup", kill the session. Otherwise, update the menu prompt.
        if (data.action === "hangup") {
            addMessage(data.message);
            endCall();
        } else {
            currentMenu = data.menu;
            addMessage(data.prompt);
        }
    });
});

// Clean up variables so we can start fresh on the next call
function endCall() {
    callActive = false;
    sessionId = null;
    currentMenu = null;
    addMessage("--- Call Ended ---");
}

document.getElementById("hangupCall").addEventListener("click", () => {
    if (callActive) endCall();
});