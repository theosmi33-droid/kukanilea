/**
 * static/js/vision_camera.js
 * Mobile Kamera-Komponente für KUKANILEA Vision.
 * Ermöglicht Fotoaufnahmen direkt in der PWA für die lokale Defektanalyse.
 */

class KukanileaVisionCamera {
    constructor() {
        this.stream = null;
        this.video = document.createElement('video');
        this.canvas = document.createElement('canvas');
        this.btn = document.getElementById('vision-camera-btn');
        this.container = document.getElementById('camera-overlay');
        this.closeBtn = document.getElementById('camera-close');
        this.shutterBtn = document.getElementById('camera-shutter');
        
        if (this.btn) {
            this.init();
        }
    }

    init() {
        this.btn.addEventListener('click', () => this.openCamera());
        if (this.closeBtn) this.closeBtn.addEventListener('click', () => this.closeCamera());
        if (this.shutterBtn) this.shutterBtn.addEventListener('click', () => this.takePhoto());
    }

    async openCamera() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ 
                video: { facingMode: "environment" }, // Nutze Rückkamera falls vorhanden
                audio: false 
            });
            
            this.video.srcObject = this.stream;
            this.video.setAttribute("playsinline", true); // Wichtig für iOS
            this.video.play();
            
            const videoContainer = document.getElementById('camera-preview');
            videoContainer.innerHTML = '';
            videoContainer.appendChild(this.video);
            
            this.container.classList.remove('hidden');
            this.container.classList.add('flex');
        } catch (err) {
            console.error("Kamera-Zugriff verweigert:", err);
            alert("KUKANILEA benötigt Zugriff auf die Kamera für die Vision-Analyse.");
        }
    }

    closeCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }
        this.container.classList.add('hidden');
        this.container.classList.remove('flex');
    }

    async takePhoto() {
        if (!this.video.videoWidth) return;

        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;
        const context = this.canvas.getContext('2d');
        context.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

        // In Blob umwandeln und senden
        this.canvas.toBlob(async (blob) => {
            this.closeCamera();
            await this.sendImage(blob);
        }, 'image/jpeg', 0.85);
    }

    async sendImage(blob) {
        if (window.toast) window.toast("Analysiere Foto...", "info");

        const formData = new FormData();
        formData.append('file', blob, 'site_analysis.jpg');

        try {
            const response = await fetch('/ai-chat/vision-analyze', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            
            if (result.status === 'ok' || result.status === 'draft') {
                this.displayResult(result);
            } else {
                if (window.toast) window.toast("Fehler bei Bildanalyse", "error");
            }
        } catch (error) {
            console.error("Vision-Transfer fehlgeschlagen:", error);
            if (window.toast) window.toast("Verbindungsfehler zur Vision-Engine", "error");
        }
    }

    displayResult(result) {
        const message = `👁️ Erkennung: "${result.description}"
🤖 ${result.agent_response}`;
        if (window.toast) {
            window.toast(message, result.is_draft ? 'warn' : 'success');
        } else {
            alert(message);
        }
        
        // Event für Dashboard-Updates (z.B. neue Materialliste)
        document.body.dispatchEvent(new CustomEvent('kukanilea:vision-result', { 
            detail: result 
        }));
    }
}

// Global initialisieren
document.addEventListener('DOMContentLoaded', () => {
    window.visionCamera = new KukanileaVisionCamera();
});
