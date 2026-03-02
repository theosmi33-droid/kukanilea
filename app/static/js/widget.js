async function sendPrompt() {
    const inputField = document.getElementById('prompt');
    const chatArea = document.getElementById('chat');
    const prompt = inputField.value.trim();

    if (!prompt) return;

    // Add user message to UI
    const userMsg = document.createElement('div');
    userMsg.className = 'message user';
    userMsg.textContent = prompt;
    chatArea.appendChild(userMsg);

    inputField.value = '';
    chatArea.scrollTop = chatArea.scrollHeight;

    // Loading indicator
    const aiMsg = document.createElement('div');
    aiMsg.className = 'message ai';
    aiMsg.textContent = 'Denke nach...';
    chatArea.appendChild(aiMsg);
    chatArea.scrollTop = chatArea.scrollHeight;

    try {
        const response = await fetch('/widget/api/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ prompt: prompt })
        });

        const data = await response.json();

        if (!response.ok) {
            aiMsg.textContent = `Fehler: ${data.error || 'Zugriff verweigert.'}`;
            aiMsg.style.color = '#f38ba8'; // Red warning
        } else {
            aiMsg.textContent = data.response;
        }
    } catch (err) {
        aiMsg.textContent = 'Netzwerkfehler zum lokalen Backend.';
        aiMsg.style.color = '#f38ba8';
    }
    chatArea.scrollTop = chatArea.scrollHeight;
}
