from pathlib import Path


def test_upload_progress_polling_is_visibility_aware_with_backoff() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "const VISIBLE_POLL_INTERVAL_MS = 1000;" in html
    assert "const HIDDEN_POLL_INTERVAL_MS = 5000;" in html
    assert "const ERROR_BACKOFF_BASE_MS = 2000;" in html
    assert "const ERROR_BACKOFF_MAX_MS = 30000;" in html
    assert 'document.addEventListener("visibilitychange"' in html
    assert "scheduleProgressPollAfterError" in html
    assert "progressPollRetryCount = 0;" in html


def test_upload_progress_polling_uses_timeout_scheduler_not_interval() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "let progressPollTimer = null;" in html
    assert "progressPollTimer = setTimeout(runProgressPoll, delayMs);" in html
    assert "if (progressPollTimer) clearTimeout(progressPollTimer);" in html


def test_upload_progress_polling_stops_cleanly_on_completion() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "const stopProgressPolling = () => {" in html
    assert "progressPollingStopped = true;" in html
    assert "if (progressPollingStopped) return;" in html
    assert "stopProgressPolling();" in html


def test_upload_progress_polling_backoff_formula_is_capped_exponential() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "ERROR_BACKOFF_BASE_MS * (2 ** (progressPollRetryCount - 1))" in html
    assert "ERROR_BACKOFF_MAX_MS" in html
    assert "Math.max(errorDelay, nextPollInterval())" in html


def test_upload_progress_polling_resets_retry_counter_after_success() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "progressPollRetryCount = 0;" in html
    assert "scheduleProgressPoll();" in html


def test_upload_progress_polling_error_path_reschedules_and_does_not_crash() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "pXhr.onerror = scheduleProgressPollAfterError;" in html
    assert "} catch (e) {" in html
    assert "scheduleProgressPollAfterError();" in html


def test_upload_progress_visibility_change_re_schedules_polling() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert 'document.addEventListener("visibilitychange", () => {' in html
    assert "if (progressPollingStopped) return;" in html
    assert "scheduleProgressPoll();" in html


def test_upload_flow_declares_progress_phase_constants() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert 'phase.textContent = "Schritt 1: Upload läuft";' in html
    assert 'phase.textContent = "Schritt 2: KI-Analyse...";' in html
    assert 'status.textContent = "Dateien werden übertragen…";' in html
    assert 'status.textContent = "Inhalte werden extrahiert...";' in html


def test_upload_flow_starts_polling_immediately_after_token_collection() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "const tokens = res.tokens.map(t => t.token);" in html
    assert "scheduleProgressPoll(0);" in html
    assert 'pXhr.open("GET", "/api/progress?tokens=" + tokens.join(","), true);' in html


def test_upload_flow_handles_partial_failures_with_warning_state() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "let failedCount = 0;" in html
    assert 'if(d.status === "ERROR") failedCount += 1;' in html
    assert 'phase.textContent = failedCount > 0 ? "Teilweise abgeschlossen" : "Abgeschlossen";' in html
    assert 'status.classList.add("text-warning");' in html


def test_upload_flow_routes_success_targets_for_single_and_multi_documents() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "if(tokens.length === 1){" in html
    assert 'setTimeout(() => window.location.href = "/review/" + tokens[0] + "/kdnr", 800);' in html
    assert 'setTimeout(() => window.location.href = "/tasks?origin=upload", 800);' in html


def test_upload_flow_exposes_error_actions_and_retry_controls() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert 'const retryBtn = document.getElementById("retryBtn");' in html
    assert 'const cancelBtn = document.getElementById("cancelBtn");' in html
    assert 'const errorActions = document.getElementById("errorActions");' in html
    assert 'retryBtn.textContent = "Erneut versuchen";' in html
    assert 'cancelBtn.textContent = "Zur Upload-Auswahl";' in html


def test_upload_flow_sets_human_readable_error_message_in_dom() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "lastErrorMessage = msg;" in html
    assert 'phase.textContent = "Unterbrochen";' in html
    assert "uploadErrorMessage.innerHTML = `<div class=\"rounded-xl border border-error/20 bg-error-bg p-3 text-sm\">${msg}</div>`;" in html
    assert 'uploadErrorMessage.style.display = "block";' in html


def test_upload_flow_resets_visual_status_on_cancel() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert 'status.classList.remove("text-error");' in html
    assert 'phase.textContent = "Initialisiere...";' in html
    assert 'status.textContent = "Analyse läuft...";' in html
    assert 'bar.style.width = "0%";' in html
    assert 'pLabel.textContent = "0.0%";' in html


def test_upload_flow_handles_drag_and_drop_states() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert 'dropZone.addEventListener("dragover", (e) => {' in html
    assert 'dropZone.classList.add("border-primary-500", "bg-primary-50");' in html
    assert 'dropZone.addEventListener("dragleave", () => {' in html
    assert 'dropZone.classList.remove("border-primary-500", "bg-primary-50");' in html
    assert 'dropZone.addEventListener("drop", (e) => {' in html


def test_upload_flow_uses_formdata_and_csrf_token() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert 'const csrfToken = "{{ csrf_token() }}";' in html
    assert "const formData = new FormData();" in html
    assert 'stagedFiles.forEach(f => formData.append("file", f));' in html
    assert 'formData.append("csrf_token", csrfToken);' in html


def test_upload_flow_requests_json_contract_response() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert 'xhr.setRequestHeader("Accept", "application/json");' in html
    assert 'if (csrfToken) xhr.setRequestHeader("X-CSRF-Token", csrfToken);' in html


def test_upload_flow_maps_read_only_errors_to_actionable_copy() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "const mapUploadErrorMessage = (xhr) => {" in html
    assert 'if (errorCode === "read_only") {' in html
    assert "Upload ist aktuell gesperrt. Bitte Lizenz in den Einstellungen aktualisieren." in html
    assert "} else { handleError(mapUploadErrorMessage(xhr)); }" in html


def test_upload_flow_falls_back_on_json_parse_failure() -> None:
    html = Path("app/templates/upload.html").read_text(encoding="utf-8")

    assert "} catch(e) { handleError(\"Die Antwort konnte nicht verarbeitet werden. Bitte erneut starten.\"); }" in html
    assert "xhr.onerror = () => handleError(\"Keine Verbindung zum Upload-Service. Bitte später erneut versuchen.\");" in html
