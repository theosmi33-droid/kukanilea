# KUKANILEA Launch Evidence Run

- Timestamp: 2026-03-05T08:57:41+00:00
- Root: `/workspace/kukanilea`
- Host: `f6f304b6f19e`
- Repo: `unknown`

## Repo/CI Evidence
`echo "LOCAL=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"; echo "REMOTE=$(git config --get remote.origin.url 2>/dev/null || echo none)"; if git show-ref --verify --quiet refs/remotes/origin/main; then echo "ORIGIN_MAIN=$(git rev-parse --short origin/main)"; else echo "ORIGIN_MAIN=unavailable"; fi`
```text
LOCAL=06f8233
REMOTE=none
ORIGIN_MAIN=unavailable
```
## Main CI Status
repo slug not detected
## Core Health
`./scripts/ops/healthcheck.sh`
```text
[healthcheck] Starting at 2026-03-05T08:57:45+00:00
[healthcheck] Root=/workspace/kukanilea
[healthcheck] Python=/root/.pyenv/versions/3.12.12/bin/python
[1/7] Python compile check...
[2/7] Ensuring DB tables...
Ensured agent_memory and api_outbound_queue in instance/auth.sqlite3
[3/7] Running unit tests...

==================================== ERRORS ====================================
_____________ ERROR collecting tests/agents/test_mail_hardening.py _____________
ImportError while importing test module '/workspace/kukanilea/tests/agents/test_mail_hardening.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/agents/test_mail_hardening.py:4: in <module>
    from app.agents.mail import MailAgent
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
_______________ ERROR collecting tests/agents/test_messenger.py ________________
ImportError while importing test module '/workspace/kukanilea/tests/agents/test_messenger.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/agents/test_messenger.py:2: in <module>
    from app.agents.orchestrator import MessengerAgent
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
__________ ERROR collecting tests/agents/test_messenger_hardening.py ___________
ImportError while importing test module '/workspace/kukanilea/tests/agents/test_messenger_hardening.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/agents/test_messenger_hardening.py:4: in <module>
    from app.agents.orchestrator import MessengerAgent, AgentContext
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
____________ ERROR collecting tests/chaos/test_prompt_injection.py _____________
ImportError while importing test module '/workspace/kukanilea/tests/chaos/test_prompt_injection.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/chaos/test_prompt_injection.py:9: in <module>
    from app.agents.llm import MockProvider
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
__________ ERROR collecting tests/contracts/test_health_contracts.py ___________
ImportError while importing test module '/workspace/kukanilea/tests/contracts/test_health_contracts.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/contracts/test_health_contracts.py:5: in <module>
    from app.contracts.tool_contracts import CONTRACT_TOOLS
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
__________ ERROR collecting tests/contracts/test_summary_contracts.py __________
ImportError while importing test module '/workspace/kukanilea/tests/contracts/test_summary_contracts.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/contracts/test_summary_contracts.py:5: in <module>
    from app.contracts.tool_contracts import CONTRACT_TOOLS
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
_________________ ERROR collecting tests/e2e/test_crdt_sync.py _________________
ImportError while importing test module '/workspace/kukanilea/tests/e2e/test_crdt_sync.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/e2e/test_crdt_sync.py:11: in <module>
    from app.core.crdt_contacts import CRDTContactManager
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
________________ ERROR collecting tests/e2e/test_ui_workflow.py ________________
ImportError while importing test module '/workspace/kukanilea/tests/e2e/test_ui_workflow.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/e2e/test_ui_workflow.py:13: in <module>
    from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect
E   ModuleNotFoundError: No module named 'playwright'
______ ERROR collecting tests/security/test_chatbot_confirm_guardrails.py ______
ImportError while importing test module '/workspace/kukanilea/tests/security/test_chatbot_confirm_guardrails.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/security/test_chatbot_confirm_guardrails.py:6: in <module>
    from flask import Flask
E   ModuleNotFoundError: No module named 'flask'
______________ ERROR collecting tests/security/test_csp_policy.py ______________
ImportError while importing test module '/workspace/kukanilea/tests/security/test_csp_policy.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/security/test_csp_policy.py:1: in <module>
    from app.security.csp import build_csp_header
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
________ ERROR collecting tests/security/test_security_gate_helpers.py _________
ImportError while importing test module '/workspace/kukanilea/tests/security/test_security_gate_helpers.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/security/test_security_gate_helpers.py:3: in <module>
    from app.security.gates import confirm_gate, detect_injection, scan_payload_for_injection
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
______ ERROR collecting tests/security/test_session_security_defaults.py _______
ImportError while importing test module '/workspace/kukanilea/tests/security/test_session_security_defaults.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/security/test_session_security_defaults.py:3: in <module>
    from app import create_app
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
_________________ ERROR collecting tests/test_ai_validator.py __________________
ImportError while importing test module '/workspace/kukanilea/tests/test_ai_validator.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_ai_validator.py:1: in <module>
    from pydantic import BaseModel
E   ModuleNotFoundError: No module named 'pydantic'
_________________ ERROR collecting tests/test_auto_learning.py _________________
ImportError while importing test module '/workspace/kukanilea/tests/test_auto_learning.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_auto_learning.py:10: in <module>
    from app.core.rag_sync import learn_from_correction
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
_________________ ERROR collecting tests/test_autonomy_ocr.py __________________
ImportError while importing test module '/workspace/kukanilea/tests/test_autonomy_ocr.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_autonomy_ocr.py:4: in <module>
    from app.autonomy.ocr import resolve_tesseract_path
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
_____________ ERROR collecting tests/test_dashboard_status_api.py ______________
ImportError while importing test module '/workspace/kukanilea/tests/test_dashboard_status_api.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_dashboard_status_api.py:5: in <module>
    from flask import Flask
E   ModuleNotFoundError: No module named 'flask'
_____________ ERROR collecting tests/test_data_integrity_paths.py ______________
ImportError while importing test module '/workspace/kukanilea/tests/test_data_integrity_paths.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_data_integrity_paths.py:3: in <module>
    from app.core.migrations import run_migrations
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
___________________ ERROR collecting tests/test_error_ux.py ____________________
ImportError while importing test module '/workspace/kukanilea/tests/test_error_ux.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_error_ux.py:3: in <module>
    from app.errors import error_envelope
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
__________________ ERROR collecting tests/test_guardrails.py ___________________
ImportError while importing test module '/workspace/kukanilea/tests/test_guardrails.py'.
Hint: make sure your test modules/packages have valid Python names.
```
## Zero-CDN Scan
`'/root/.pyenv/versions/3.12.12/bin/python' scripts/ops/verify_guardrails.py`
```text
[GUARDRAIL] Verifying CDN and HTMX confirm gates...
OK: All guardrail checks passed.
```
## White-Mode Evidence
`rg -n "dark:|themeToggle|classList\.(add|toggle)\(("dark"|'dark')\)" app/templates app/static --glob '!app/static/vendor/**' --glob '!app/static/js/tailwindcss.min.js' || true`
```text
(no output)
```
## License Evidence Matrix
.........                                                                [100%]
============================= slowest 10 durations =============================

(10 durations < 0.005s hidden.  Use -vv to show these durations.)
9 passed in 0.04s
```text
.........                                                                [100%]
============================= slowest 10 durations =============================

(10 durations < 0.005s hidden.  Use -vv to show these durations.)
9 passed in 0.05s
```
21:    assert normalize_status_hint("aktiv") == "active"
22:    assert normalize_status_hint("gesperrt") == "blocked"
23:    assert normalize_status_hint("locked") == "blocked"
27:def test_active_state_is_writable() -> None:
28:    out = evaluate_license_state(LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="active"))
29:    assert out["status"] == "active"
33:def test_grace_state_remains_writable() -> None:
34:    out = evaluate_license_state(LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="grace"))
35:    assert out["status"] == "grace"
39:def test_blocked_with_smb_unreachable_stays_blocked() -> None:
41:        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="blocked", smb_reachable=False)
43:    assert out["status"] == "blocked"
44:    assert out["reason"] == "license_blocked_smb_unreachable"
47:def test_blocked_with_smb_reachable_enters_recover() -> None:
49:        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="blocked", smb_reachable=True)
53:    assert out["transition"] == "blocked->recover"
56:def test_recover_to_active_when_smb_available() -> None:
60:    assert out["status"] == "active"
62:    assert out["transition"] == "recover->active"
65:def test_device_mismatch_forces_blocked() -> None:
67:        LicenseInputs(valid=True, expired=False, device_mismatch=True, status_hint="active", smb_reachable=True)
69:    assert out["status"] == "blocked"
73:def test_locked_alias_behaves_like_blocked() -> None:
78:    assert out["transition"] == "blocked->recover"
81:def test_recovery_alias_returns_to_active() -> None:
85:    assert out["status"] == "active"
```text
21:    assert normalize_status_hint("aktiv") == "active"
22:    assert normalize_status_hint("gesperrt") == "blocked"
23:    assert normalize_status_hint("locked") == "blocked"
27:def test_active_state_is_writable() -> None:
28:    out = evaluate_license_state(LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="active"))
29:    assert out["status"] == "active"
33:def test_grace_state_remains_writable() -> None:
34:    out = evaluate_license_state(LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="grace"))
35:    assert out["status"] == "grace"
39:def test_blocked_with_smb_unreachable_stays_blocked() -> None:
41:        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="blocked", smb_reachable=False)
43:    assert out["status"] == "blocked"
44:    assert out["reason"] == "license_blocked_smb_unreachable"
47:def test_blocked_with_smb_reachable_enters_recover() -> None:
49:        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="blocked", smb_reachable=True)
53:    assert out["transition"] == "blocked->recover"
56:def test_recover_to_active_when_smb_available() -> None:
60:    assert out["status"] == "active"
62:    assert out["transition"] == "recover->active"
65:def test_device_mismatch_forces_blocked() -> None:
67:        LicenseInputs(valid=True, expired=False, device_mismatch=True, status_hint="active", smb_reachable=True)
69:    assert out["status"] == "blocked"
73:def test_locked_alias_behaves_like_blocked() -> None:
78:    assert out["transition"] == "blocked->recover"
81:def test_recovery_alias_returns_to_active() -> None:
85:    assert out["status"] == "active"
```
## Chat/Guardrail Evidence
`rg -n "chat|messenger|guardrail|policy" app/templates app/static/js scripts/ops/verify_guardrails.py || true`
```text
scripts/ops/verify_guardrails.py:73:        print("OK: All guardrail checks passed.")
app/templates/messenger.html:16:  .ms-chat { display:flex; flex-direction:column; min-height: calc(100vh - 170px); }
app/templates/messenger.html:32:  @media (max-width: 1100px) { .ms-hub { grid-template-columns: 1fr; } .ms-list{max-height:220px;} .ms-chat{min-height:420px;} }
app/templates/messenger.html:47:  <main class="ms-card ms-chat">
app/templates/messenger.html:51:        <div id="thread-sub" class="ms-sub">Interner Teamchat • offline always</div>
app/templates/messenger.html:86:  const STORE_KEY = 'kuka_messenger_hub_v2';
app/templates/messenger.html:187:      ? 'Interner Teamchat • offline always'
app/templates/messenger.html:282:      if (/telegram|meta|instagram|whatsapp|messenger/i.test(text)) addAction('send_external', 'Externe Nachricht senden (Provider-Policy prüfen)', true);
app/templates/layout.html:88:  <div id="ki-chat-widget" style="position: fixed; bottom: 24px; right: 24px; z-index: 1000; display: flex; flex-direction: column; align-items: flex-end; gap: 12px;">
app/templates/layout.html:89:    <div id="ki-chat-window" style="display: none; width: 350px; height: 450px; background: var(--bg-secondary); border: 1px solid var(--color-border); border-radius: 16px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3); flex-direction: column; overflow: hidden; backdrop-filter: blur(10px);">
app/templates/layout.html:99:        <div id="chat-messages" style="flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; font-size: 13px;">
app/templates/layout.html:105:            <input type="text" id="chat-input" placeholder="Nachricht schreiben..." style="flex: 1; background: var(--bg-tertiary); border: 1px solid var(--color-border); border-radius: 8px; padding: 8px 12px; color: var(--text-primary); font-size: 13px; outline: none;">
app/templates/layout.html:106:            <button id="chat-send-btn" onclick="sendChatMessage()" style="background: var(--color-primary); color: white; border: none; border-radius: 8px; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; cursor: pointer;">
app/templates/layout.html:148:      const win = document.getElementById('ki-chat-window');
app/templates/layout.html:152:      if (isHidden) document.getElementById('chat-input')?.focus();
app/templates/layout.html:156:      const container = document.getElementById('chat-messages');
app/templates/layout.html:168:      const input = document.getElementById('chat-input');
app/templates/layout.html:169:      const sendBtn = document.getElementById('chat-send-btn');
app/templates/layout.html:182:        const res = await fetch('/api/chat', {
app/templates/layout.html:217:    document.getElementById('chat-input')?.addEventListener('keydown', function (e) {
app/templates/partials/floating_chat.html:2:<section id="floating-chat-widget" class="floating-chat-widget" data-widget="chatbot" hidden>
app/templates/partials/floating_chat.html:4:    id="floating-chat-toggle"
app/templates/partials/floating_chat.html:6:    class="floating-chat-toggle"
app/templates/partials/floating_chat.html:7:    aria-controls="floating-chat-panel"
app/templates/partials/floating_chat.html:11:    <span class="floating-chat-toggle-label">KI</span>
app/templates/partials/floating_chat.html:12:    <span id="floating-chat-unread-badge" class="floating-chat-unread-badge" hidden>0</span>
app/templates/partials/floating_chat.html:16:    id="floating-chat-panel"
app/templates/partials/floating_chat.html:17:    class="floating-chat-panel"
app/templates/partials/floating_chat.html:23:    <header class="floating-chat-header">
app/templates/partials/floating_chat.html:24:      <div class="floating-chat-title-wrap">
app/templates/partials/floating_chat.html:25:        <h3 class="floating-chat-title">AI Companion</h3>
app/templates/partials/floating_chat.html:26:        <p id="floating-chat-status" class="floating-chat-status">Bereit</p>
app/templates/partials/floating_chat.html:28:      <div class="floating-chat-controls">
app/templates/partials/floating_chat.html:29:        <button id="floating-chat-minimize" type="button" class="floating-chat-icon-btn" aria-label="Minimieren">_</button>
app/templates/partials/floating_chat.html:30:        <button id="floating-chat-close" type="button" class="floating-chat-icon-btn" aria-label="Schließen">x</button>
app/templates/partials/floating_chat.html:34:    <div id="floating-chat-context-tag" class="floating-chat-context-tag">Kontext: /</div>
app/templates/partials/floating_chat.html:35:    <div id="floating-chat-quick-actions" class="floating-chat-quick-actions"></div>
app/templates/partials/floating_chat.html:37:    <div id="floating-chat-body" class="floating-chat-body">
app/templates/partials/floating_chat.html:38:      <ul id="floating-chat-messages" class="floating-chat-messages" aria-live="polite" aria-relevant="additions"></ul>
app/templates/partials/floating_chat.html:39:      <div id="floating-chat-thinking" class="floating-chat-thinking" hidden>
app/templates/partials/floating_chat.html:40:        <span class="floating-chat-thinking-dot"></span>
app/templates/partials/floating_chat.html:43:      <ol id="floating-chat-steps" class="floating-chat-steps"></ol>
app/templates/partials/floating_chat.html:46:    <div id="floating-chat-confirm" class="floating-chat-confirm" hidden>
app/templates/partials/floating_chat.html:47:      <p id="floating-chat-confirm-text"></p>
app/templates/partials/floating_chat.html:48:      <div class="floating-chat-confirm-actions">
app/templates/partials/floating_chat.html:49:        <button id="floating-chat-confirm-yes" type="button" class="btn btn-primary btn-sm">Ja, ausführen</button>
app/templates/partials/floating_chat.html:50:        <button id="floating-chat-confirm-no" type="button" class="btn btn-secondary btn-sm">Abbrechen</button>
app/templates/partials/floating_chat.html:54:    <form id="floating-chat-form" class="floating-chat-form" autocomplete="off">
app/templates/partials/floating_chat.html:55:      <label for="floating-chat-input" class="sr-only">Nachricht</label>
app/templates/partials/floating_chat.html:56:      <input id="floating-chat-input" name="message" type="text" maxlength="600" placeholder="Wie kann ich helfen?" />
app/templates/partials/floating_chat.html:57:      <button id="floating-chat-send" type="submit" class="btn btn-primary btn-sm">Senden</button>
app/static/js/vision_camera.js:81:            const response = await fetch('/ai-chat/vision-analyze', {
app/templates/partials/sidebar.html:33:      <a href="/messenger" data-route="/messenger" class="nav-link {{ 'active' if request.path.startswith('/messenger') }}">
app/static/js/voice_recorder.js:83:            const response = await fetch('/ai-chat/transcribe', {
app/static/js/chatbot.js:9:    root: document.getElementById("floating-chat-widget"),
app/static/js/chatbot.js:10:    toggle: document.getElementById("floating-chat-toggle"),
app/static/js/chatbot.js:11:    panel: document.getElementById("floating-chat-panel"),
app/static/js/chatbot.js:12:    body: document.getElementById("floating-chat-body"),
app/static/js/chatbot.js:13:    close: document.getElementById("floating-chat-close"),
app/static/js/chatbot.js:14:    minimize: document.getElementById("floating-chat-minimize"),
app/static/js/chatbot.js:15:    unread: document.getElementById("floating-chat-unread-badge"),
app/static/js/chatbot.js:16:    status: document.getElementById("floating-chat-status"),
app/static/js/chatbot.js:17:    contextTag: document.getElementById("floating-chat-context-tag"),
app/static/js/chatbot.js:18:    quickActions: document.getElementById("floating-chat-quick-actions"),
app/static/js/chatbot.js:19:    messages: document.getElementById("floating-chat-messages"),
app/static/js/chatbot.js:20:    thinking: document.getElementById("floating-chat-thinking"),
app/static/js/chatbot.js:21:    steps: document.getElementById("floating-chat-steps"),
app/static/js/chatbot.js:22:    confirm: document.getElementById("floating-chat-confirm"),
app/static/js/chatbot.js:23:    confirmText: document.getElementById("floating-chat-confirm-text"),
app/static/js/chatbot.js:24:    confirmYes: document.getElementById("floating-chat-confirm-yes"),
app/static/js/chatbot.js:25:    confirmNo: document.getElementById("floating-chat-confirm-no"),
app/static/js/chatbot.js:26:    form: document.getElementById("floating-chat-form"),
app/static/js/chatbot.js:27:    input: document.getElementById("floating-chat-input"),
app/static/js/chatbot.js:161:    li.className = "floating-chat-msg floating-chat-msg-" + kind;
app/static/js/chatbot.js:164:    bubble.className = "floating-chat-bubble";
app/static/js/chatbot.js:170:      small.className = "floating-chat-meta";
app/static/js/chatbot.js:273:      btn.className = "floating-chat-quick-action btn btn-secondary btn-sm";
app/static/js/chatbot.js:282:      const response = await fetch("/api/chat/compact?history=1&limit=30", {
app/static/js/chatbot.js:344:      const response = await fetch("/api/chat/compact", {
```
## VSCode Guardrails
`bash scripts/dev/vscode_guardrails.sh --check`
```text
warning: missing interpreter /workspace/kukanilea/.build_venv/bin/python (using /root/.pyenv/shims/python3)
vscode-configs: OK
```
## Overlap Matrix
`bash scripts/orchestration/overlap_matrix_11.sh`
```text
/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/reviews/codex/OVERLAP_MATRIX_11_20260305_085803.md
```
## Pytest
`'/root/.pyenv/versions/3.12.12/bin/python' -m pytest -q`
```text

==================================== ERRORS ====================================
_____________ ERROR collecting tests/agents/test_mail_hardening.py _____________
ImportError while importing test module '/workspace/kukanilea/tests/agents/test_mail_hardening.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/agents/test_mail_hardening.py:4: in <module>
    from app.agents.mail import MailAgent
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
_______________ ERROR collecting tests/agents/test_messenger.py ________________
ImportError while importing test module '/workspace/kukanilea/tests/agents/test_messenger.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/agents/test_messenger.py:2: in <module>
    from app.agents.orchestrator import MessengerAgent
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
__________ ERROR collecting tests/agents/test_messenger_hardening.py ___________
ImportError while importing test module '/workspace/kukanilea/tests/agents/test_messenger_hardening.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/agents/test_messenger_hardening.py:4: in <module>
    from app.agents.orchestrator import MessengerAgent, AgentContext
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
____________ ERROR collecting tests/chaos/test_prompt_injection.py _____________
ImportError while importing test module '/workspace/kukanilea/tests/chaos/test_prompt_injection.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/chaos/test_prompt_injection.py:9: in <module>
    from app.agents.llm import MockProvider
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
__________ ERROR collecting tests/contracts/test_health_contracts.py ___________
ImportError while importing test module '/workspace/kukanilea/tests/contracts/test_health_contracts.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/contracts/test_health_contracts.py:5: in <module>
    from app.contracts.tool_contracts import CONTRACT_TOOLS
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
__________ ERROR collecting tests/contracts/test_summary_contracts.py __________
ImportError while importing test module '/workspace/kukanilea/tests/contracts/test_summary_contracts.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/contracts/test_summary_contracts.py:5: in <module>
    from app.contracts.tool_contracts import CONTRACT_TOOLS
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
_________________ ERROR collecting tests/e2e/test_crdt_sync.py _________________
ImportError while importing test module '/workspace/kukanilea/tests/e2e/test_crdt_sync.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/e2e/test_crdt_sync.py:11: in <module>
    from app.core.crdt_contacts import CRDTContactManager
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
________________ ERROR collecting tests/e2e/test_ui_workflow.py ________________
ImportError while importing test module '/workspace/kukanilea/tests/e2e/test_ui_workflow.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/e2e/test_ui_workflow.py:13: in <module>
    from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect
E   ModuleNotFoundError: No module named 'playwright'
______ ERROR collecting tests/security/test_chatbot_confirm_guardrails.py ______
ImportError while importing test module '/workspace/kukanilea/tests/security/test_chatbot_confirm_guardrails.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/security/test_chatbot_confirm_guardrails.py:6: in <module>
    from flask import Flask
E   ModuleNotFoundError: No module named 'flask'
______________ ERROR collecting tests/security/test_csp_policy.py ______________
ImportError while importing test module '/workspace/kukanilea/tests/security/test_csp_policy.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/security/test_csp_policy.py:1: in <module>
    from app.security.csp import build_csp_header
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
________ ERROR collecting tests/security/test_security_gate_helpers.py _________
ImportError while importing test module '/workspace/kukanilea/tests/security/test_security_gate_helpers.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/security/test_security_gate_helpers.py:3: in <module>
    from app.security.gates import confirm_gate, detect_injection, scan_payload_for_injection
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
______ ERROR collecting tests/security/test_session_security_defaults.py _______
ImportError while importing test module '/workspace/kukanilea/tests/security/test_session_security_defaults.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/security/test_session_security_defaults.py:3: in <module>
    from app import create_app
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
_________________ ERROR collecting tests/test_ai_validator.py __________________
ImportError while importing test module '/workspace/kukanilea/tests/test_ai_validator.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_ai_validator.py:1: in <module>
    from pydantic import BaseModel
E   ModuleNotFoundError: No module named 'pydantic'
_________________ ERROR collecting tests/test_auto_learning.py _________________
ImportError while importing test module '/workspace/kukanilea/tests/test_auto_learning.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_auto_learning.py:10: in <module>
    from app.core.rag_sync import learn_from_correction
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
_________________ ERROR collecting tests/test_autonomy_ocr.py __________________
ImportError while importing test module '/workspace/kukanilea/tests/test_autonomy_ocr.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_autonomy_ocr.py:4: in <module>
    from app.autonomy.ocr import resolve_tesseract_path
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
_____________ ERROR collecting tests/test_dashboard_status_api.py ______________
ImportError while importing test module '/workspace/kukanilea/tests/test_dashboard_status_api.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_dashboard_status_api.py:5: in <module>
    from flask import Flask
E   ModuleNotFoundError: No module named 'flask'
_____________ ERROR collecting tests/test_data_integrity_paths.py ______________
ImportError while importing test module '/workspace/kukanilea/tests/test_data_integrity_paths.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_data_integrity_paths.py:3: in <module>
    from app.core.migrations import run_migrations
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
___________________ ERROR collecting tests/test_error_ux.py ____________________
ImportError while importing test module '/workspace/kukanilea/tests/test_error_ux.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_error_ux.py:3: in <module>
    from app.errors import error_envelope
app/__init__.py:7: in <module>
    from flask import Flask, request, session
E   ModuleNotFoundError: No module named 'flask'
__________________ ERROR collecting tests/test_guardrails.py ___________________
ImportError while importing test module '/workspace/kukanilea/tests/test_guardrails.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/root/.pyenv/versions/3.12.12/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_guardrails.py:6: in <module>
    from app.ai.guardrails import validate_prompt
app/__init__.py:7: in <module>
```
## KPI Snapshot
`./scripts/ops/kpi_snapshot.sh`
```text
/workspace/kukanilea/docs/status/KPI_SNAPSHOT_20260305_085807.md
```

## Result Matrix

| Gate | Status | Note |
|---|---|---|
| Repo/CI Evidence | WARN | origin/main unavailable in local clone (LOCAL=06f8233) |
| Main CI Status | WARN | repo slug missing (set REPO=owner/name) |
| Core Health | FAIL | core healthcheck failed |
| Zero-CDN Scan | PASS | command succeeded |
| White-Mode Evidence | PASS | no dark mode toggle signatures found |
| License Evidence Matrix | PASS | AKTIV/GRACE/GESPERRT transitions covered |
| Chat/Guardrail Evidence | PASS | chat/guardrail markers detected |
| VSCode Guardrails | PASS | command succeeded |
| Overlap Matrix | PASS | command succeeded |
| Pytest | FAIL | pytest execution failed |
| KPI Snapshot | PASS | command succeeded |

## Decision

**NO-GO**

- PASS: 7
- WARN: 2
- FAIL: 2
