/**
 * KUKANILEA Upload Engine v3.1
 * Extracted for G3 Workflow Modernization
 */
document.addEventListener("DOMContentLoaded", function() {
  const fileInput = document.getElementById("file");
  const stagingArea = document.getElementById("stagingArea");
  const fileList = document.getElementById("fileList");
  const fileCount = document.getElementById("fileCount");
  const clearStaging = document.getElementById("clearStaging");
  const startBtn = document.getElementById("startAnalysis");
  const progressArea = document.getElementById("progressArea");
  const bar = document.getElementById("bar");
  const pLabel = document.getElementById("pLabel");
  const status = document.getElementById("status");
  const phase = document.getElementById("phase");
  const dropZone = document.getElementById("dropZone");

  let stagedFiles = [];

  const updateUI = () => {
    if (!fileList) return;
    fileList.innerHTML = "";
    stagedFiles.forEach((f, i) => {
      const d = document.createElement("div");
      d.className = "wf-card p-4 flex items-center justify-between border-light bg-secondary shadow-none";
      d.innerHTML = `
        <div class="flex items-center gap-3 overflow-hidden">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-muted shrink-0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <div class="truncate text-xs font-bold text-main">${f.name}</div>
        </div>
        <button class="btn btn-ghost btn-xs text-error" onclick="window._rm(${i})">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
        </button>
      `;
      fileList.appendChild(d);
    });
    if (fileCount) fileCount.textContent = stagedFiles.length;
    if (stagingArea) stagingArea.style.display = stagedFiles.length > 0 ? "flex" : "none";
    if (dropZone) dropZone.style.display = stagedFiles.length > 0 ? "none" : "block";
  };

  window._rm = (idx) => { stagedFiles.splice(idx, 1); updateUI(); };

  if (clearStaging) {
    clearStaging.addEventListener("click", () => { stagedFiles = []; updateUI(); if (fileInput) fileInput.value = ""; });
  }

  if (fileInput) {
    fileInput.addEventListener("change", () => {
      stagedFiles = [...stagedFiles, ...Array.from(fileInput.files)];
      updateUI();
    });
  }

  if (dropZone) {
    dropZone.addEventListener("dragover", (e) => { 
      e.preventDefault(); 
      dropZone.classList.add("active");
    });
    dropZone.addEventListener("dragleave", () => { 
      dropZone.classList.remove("active");
    });
    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.classList.remove("active");
      if(e.dataTransfer.files.length > 0){
        stagedFiles = [...stagedFiles, ...Array.from(e.dataTransfer.files)];
        updateUI();
      }
    });
  }

  // Get CSRF from meta tag if available
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
  
  const uploadAction = () => {
    if(stagedFiles.length === 0) return;
    if (stagingArea) stagingArea.style.display = "none";
    if (progressArea) progressArea.style.display = "block";
    const errorActions = document.getElementById("errorActions");
    if (errorActions) errorActions.style.display = "none";
    
    const formData = new FormData();
    stagedFiles.forEach(f => formData.append("file", f));
    formData.append("csrf_token", csrfToken);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/upload", true);
    let targetProgress = 0, currentProgress = 0;

    const sim = setInterval(() => {
      if(currentProgress < targetProgress) currentProgress += 0.5;
      if (bar) bar.style.width = currentProgress + "%";
      if (pLabel) pLabel.textContent = currentProgress.toFixed(1) + "%";
    }, 30);

    xhr.upload.onprogress = (ev) => {
      if(ev.lengthComputable){
        targetProgress = (ev.loaded / ev.total) * 35;
        if (phase) phase.textContent = "Übertragung...";
      }
    };

    xhr.onload = () => {
      if(xhr.status === 200){
        try {
          const res = JSON.parse(xhr.responseText);
          if(res.tokens && res.tokens.length > 0){
            const tokens = res.tokens.map(t => t.token);
            targetProgress = 35;
            if (phase) phase.textContent = "KI-Analyse...";
            if (status) status.textContent = "Datenextraktion...";

            const check = setInterval(() => {
              const pXhr = new XMLHttpRequest();
              pXhr.open("GET", "/api/progress?tokens=" + tokens.join(","), true);
              pXhr.onload = () => {
                if(pXhr.status === 200){
                  const data = JSON.parse(pXhr.responseText);
                  let allDone = true;
                  let minP = 100;
                  Object.values(data).forEach(d => {
                    if(d.status !== "READY" && d.status !== "ERROR") allDone = false;
                    if(d.progress < minP) minP = d.progress;
                  });
                  targetProgress = 35 + (minP * 0.65);
                  if(allDone){
                    clearInterval(check);
                    clearInterval(sim);
                    if (bar) bar.style.width = "100%";
                    if (pLabel) pLabel.textContent = "100%";
                    if (phase) phase.textContent = "Abgeschlossen";
                    if (status) status.textContent = "Analyse fertig.";
                    if(tokens.length === 1){
                      setTimeout(() => window.location.href = "/review/" + tokens[0] + "/kdnr", 800);
                    } else {
                      setTimeout(() => window.location.href = "/dashboard", 800);
                    }
                  }
                }
              };
              pXhr.send();
            }, 1000);
          }
        } catch(e) { handleError("Server-Fehler."); }
      } else { handleError("Upload fehlgeschlagen."); }
    };

    const handleError = (msg) => {
      clearInterval(sim);
      if (status) {
        status.textContent = msg;
        status.classList.add("text-error");
      }
      if (errorActions) errorActions.style.display = "flex";
    };
    
    xhr.send(formData);
  };

  if (startBtn) {
    startBtn.addEventListener("click", uploadAction);
  }
});
