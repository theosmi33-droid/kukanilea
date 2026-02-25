"""
tests/e2e/test_fleet_cockpit.py
Automatisierter End-to-End Audit für den Global Mesh Monitor.
Verifiziert Graceful Degradation und HTMX-Polling via Playwright Network Interception.
"""

import pytest
import re
from playwright.sync_api import Page, expect, Route

BASE_URL = "http://127.0.0.1:8080"

# Mock Payload A: Healthy State (Normalbetrieb)
HTML_HEALTHY = """
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  <!-- Hub Card (Healthy) -->
  <div class="card p-6 rounded-2xl border-2 border-indigo-500/20 bg-indigo-50/5 relative overflow-hidden">
    <h2 class="text-xl font-bold">Workshop Hub</h2>
    <div class="space-y-4 mt-4">
      <div class="flex justify-between items-center pb-2 border-b border-zinc-100">
        <span class="text-xs text-zinc-500 uppercase font-semibold">CPU Temp</span>
        <span id="temp-badge" class="text-sm font-bold text-emerald-600">45°C</span>
      </div>
    </div>
    <div class="mt-6 pt-4 border-t border-indigo-500/10">
      <div id="backup-badge" class="flex items-center gap-2 p-2 rounded-lg bg-emerald-50 border border-emerald-100">
        <span class="text-xs font-semibold text-emerald-700 block">Signatur Verifiziert</span>
      </div>
    </div>
  </div>
  <!-- Peer Card (Healthy) -->
  <div id="peer-card" class="card p-6 rounded-2xl border border-zinc-200">
    <div class="flex justify-between items-start mb-6">
      <h2 class="text-lg font-bold">Tablet-Lehrling</h2>
      <div id="peer-status" class="px-2 py-1 bg-emerald-100 text-emerald-700 text-[9px] font-black uppercase tracking-widest rounded-md">Online</div>
    </div>
  </div>
</div>
"""

# Mock Payload B: Critical State (Thermal Warning & Offline Peer)
HTML_CRITICAL = """
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  <!-- Hub Card (Critical) -->
  <div class="card p-6 rounded-2xl border-2 border-indigo-500/20 bg-indigo-50/5 relative overflow-hidden">
    <h2 class="text-xl font-bold">Workshop Hub</h2>
    <div class="space-y-4 mt-4">
      <div class="flex justify-between items-center pb-2 border-b border-zinc-100">
        <span class="text-xs text-zinc-500 uppercase font-semibold">CPU Temp</span>
        <span id="temp-badge" class="text-sm font-bold text-rose-600 bg-rose-50 px-2 py-0.5 rounded animate-pulse">85°C</span>
      </div>
    </div>
    <div class="mt-6 pt-4 border-t border-indigo-500/10">
      <div id="backup-badge" class="flex items-center gap-2 p-2 rounded-lg bg-emerald-50 border border-emerald-100">
        <span class="text-xs font-semibold text-emerald-700 block">Signatur Verifiziert</span>
      </div>
    </div>
  </div>
  <!-- Peer Card (Critical / Offline) -->
  <div id="peer-card" class="card p-6 rounded-2xl border border-rose-500/30 bg-rose-50/20 opacity-80 shadow-md shadow-rose-500/5">
    <div class="flex justify-between items-start mb-6">
      <h2 class="text-lg font-bold">Tablet-Lehrling</h2>
      <div id="peer-status" class="px-2 py-1 bg-rose-100 text-rose-700 text-[9px] font-black uppercase tracking-widest rounded-md shadow-sm">Offline</div>
    </div>
  </div>
</div>
"""

@pytest.fixture(autouse=True)
def setup_auth(page: Page):
    """Bypass Authentication."""
    page.goto(f"{BASE_URL}/health")
    yield

def test_fleet_cockpit_graceful_degradation(page: Page):
    state = {"call_count": 0}

    def handle_route(route: Route):
        # Bei erstem Aufruf Payload A, bei nachfolgenden Payload B
        if state["call_count"] == 0:
            route.fulfill(status=200, content_type="text/html", body=HTML_HEALTHY)
        else:
            route.fulfill(status=200, content_type="text/html", body=HTML_CRITICAL)
        state["call_count"] += 1

    # Playwright Interception für den HTMX Polling Endpunkt
    page.route("**/api/p2p/fleet/status", handle_route)

    # 1. UI Assertion (Healthy State)
    page.goto(f"{BASE_URL}/admin/mesh")
    
    # Warte auf das initiale Rendern durch HTMX
    expect(page.locator("h2:has-text('Workshop Hub')")).to_be_visible()
    
    # Prüfe gesunden Temperatur-Badge (nicht rot)
    temp_badge = page.locator("#temp-badge")
    expect(temp_badge).to_have_text("45°C")
    expect(temp_badge).not_to_have_class(re.compile(r"text-rose-600"))
    
    # Prüfe Online-Status des Peers
    peer_status = page.locator("#peer-status")
    expect(peer_status).to_have_text("Online")
    expect(peer_status).to_have_class(re.compile(r"bg-emerald-100"))

    print("\n[AUDIT] Healthy State (Payload A) erfolgreich verifiziert.")

    # 2. UI Assertion (Critical State / Graceful Degradation)
    # Wir warten auf den natürlichen 5s Polling-Zyklus von HTMX (hx-trigger="load, every 5s")
    page.wait_for_timeout(5500)
    
    # Wir erwarten nun, dass die Klasse auf rot (rose) wechselt ohne Page Reload
    expect(temp_badge).to_have_text("85°C", timeout=5000)
    expect(temp_badge).to_have_class(re.compile(r"text-rose-600"))
    expect(temp_badge).to_have_class(re.compile(r"animate-pulse"))
    
    # Peer muss nun als Offline und visuell ausgegraut markiert sein
    expect(peer_status).to_have_text("Offline")
    expect(peer_status).to_have_class(re.compile(r"bg-rose-100"))
    
    peer_card = page.locator("#peer-card")
    expect(peer_card).to_have_class(re.compile(r"opacity-80"))

    print("[AUDIT] Critical State & HTMX Graceful Degradation erfolgreich verifiziert.")
