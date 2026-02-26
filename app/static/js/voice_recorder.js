/**
 * static/js/voice_recorder.js
 * Mobile Sprachsteuerung für KUKANILEA PWA.
 * Erfasst Audio-Blobs und sendet sie an den lokalen STT-Endpunkt.
 */

class KukanileaVoiceRecorder {
    constructor() {
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.btn = document.getElementById('voice-record-btn');
        this.statusIndicator = document.getElementById('voice-status');
        
        if (this.btn) {
            this.init();
        }
    }

    init() {
        this.btn.addEventListener('click', () => {
            if (this.isRecording) {
                this.stop();
            } else {
                this.start();
            }
        });
    }

    async start() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(stream);
            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };

            this.mediaRecorder.onstop = () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
                this.sendAudio(audioBlob);
            };

            this.mediaRecorder.start();
            this.isRecording = true;
            this.updateUI(true);
            console.log("KUKANILEA Voice: Aufnahme gestartet...");
        } catch (err) {
            console.error("Mikrofon-Zugriff verweigert:", err);
            alert("KUKANILEA benötigt Zugriff auf das Mikrofon für die Sprachsteuerung.");
        }
    }

    stop() {
        if (this.mediaRecorder) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.updateUI(false);
            
            // Stop stream tracks
            this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
    }

    updateUI(recording) {
        if (recording) {
            this.btn.classList.add('recording-active');
            this.statusIndicator.innerText = "Höre zu...";
            this.statusIndicator.classList.remove('hidden');
        } else {
            this.btn.classList.remove('recording-active');
            this.statusIndicator.innerText = "Verarbeite...";
        }
    }

    async sendAudio(blob) {
        const formData = new FormData();
        formData.append('file', blob, 'mobile_voice.wav');

        try {
            // Wir nutzen den FastAPI-Endpunkt als Default
            const response = await fetch('/ai-chat/transcribe', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            
            if (result.status === 'ok' || result.status === 'draft') {
                this.displayResult(result);
            } else {
                this.statusIndicator.innerText = "Fehler bei STT";
            }
        } catch (error) {
            console.error("Audio-Transfer fehlgeschlagen:", error);
            this.statusIndicator.innerText = "Verbindungsfehler";
        } finally {
            setTimeout(() => {
                this.statusIndicator.classList.add('hidden');
            }, 3000);
        }
    }

    displayResult(result) {
        // Integration in das bestehende Chat-UI oder als Toast-Notification
        console.log("STT Result:", result);
        
        const message = `🎤 "${result.transcription}"
🤖 ${result.agent_response}`;
        
        // Falls HTMX genutzt wird, triggern wir ein Event
        document.body.dispatchEvent(new CustomEvent('kukanilea:voice-command', { 
            detail: result 
        }));

        if (window.toast) {
            window.toast(message, result.is_draft ? 'warn' : 'success');
        } else {
            alert(message);
        }
    }
}

// Global initialisieren
document.addEventListener('DOMContentLoaded', () => {
    window.voiceRecorder = new KukanileaVoiceRecorder();
});
