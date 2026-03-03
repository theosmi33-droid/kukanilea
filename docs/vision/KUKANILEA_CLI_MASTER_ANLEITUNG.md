# 🤖 KUKANILEA – CLI-MASTER-ANLEITUNG (Codex + Gemini)

**Ziel:** Maximale Tool-Performance + Harmonische Zusammenarbeit via AI-CLI  
**Tools:** VS Code Cursor/Windsurf (Codex) + Google Gemini CLI  
**Scope:** 11 Worktrees Integration + Sovereign-11 Shell  
**Datum:** 03. März 2026

---

## 📋 INHALTSVERZEICHNIS

1. [Setup: Codex + Gemini CLI](#1-setup-codex--gemini-cli)
2. [Die 11 Worktrees: Struktur & Ownership](#2-die-11-worktrees-struktur--ownership)
3. [Workflow: Pro-Worktree-Integration](#3-workflow-pro-worktree-integration)
4. [Codex-Prompts: Copy-Paste-Ready](#4-codex-prompts-copy-paste-ready)
5. [Gemini CLI: Batch-Operations](#5-gemini-cli-batch-operations)
6. [Automatisierung: Scripts für beide CLIs](#6-automatisierung-scripts-für-beide-clis)
7. [Integration-Pipeline: Step-by-Step](#7-integration-pipeline-step-by-step)
8. [Troubleshooting & Best Practices](#8-troubleshooting--best-practices)

---

## 1. SETUP: Codex + Gemini CLI

### 1.1 Codex (VS Code Cursor/Windsurf) einrichten

**Was ist Codex?**  
Cursor/Windsurf sind VS Code-Forks mit integrierter AI (Claude/GPT). Perfekt für Codebase-weite Änderungen.

**Installation:**

```bash
# Option A: Cursor
brew install --cask cursor

# Option B: Windsurf (falls Cursor nicht verfügbar)
brew install --cask windsurf

# Starte Cursor
cursor /Users/gensuminguyen/Kukanilea/kukanilea_production
```

**Konfiguration für KUKANILEA:**

Erstelle `.cursor/settings.json` im Projekt-Root:

```json
{
  "cursor.ai.model": "claude-sonnet-4-20250514",
  "cursor.ai.maxTokens": 8000,
  "cursor.ai.temperature": 0.2,
  "cursor.composer.enabled": true,
  "cursor.chat.contextFiles": [
    "docs/SOVEREIGN_11_FINAL_PACKAGE.md",
    "docs/MASTER_ENGINEERING_PROMPT.md",
    "docs/TAB_OWNERSHIP_RULES.md",
    "contracts/CORE_TOOL_INTERFACE.md"
  ],
  "cursor.rules": [
    "NEVER edit files in app/static/vendor/ (shell-owned)",
    "NEVER edit app/templates/layout.html without Scope-Request",
    "ALWAYS use 8pt-Grid spacing (multiples of 8px)",
    "ALWAYS implement ToolInterface for new tools",
    "ALWAYS write tests for new features"
  ]
}
```

**Custom Cursor Rules (`.cursorrules` file):**

```markdown
# KUKANILEA Cursor Rules

## Core Principles
- White-Mode ONLY (no dark-mode code)
- 8pt-Grid spacing system (8, 16, 24, 32, 40, 48px)
- WCAG AA contrast ratios
- Zero external CDNs
- Offline-First by default

## Shell Ownership
The following files are CORE-OWNED (Scope-Request required):
- app/templates/layout.html
- app/templates/partials/sidebar.html
- app/static/css/sovereign-shell.css
- app/static/icons/sprite.svg
- app/static/fonts/*
- app/static/js/navigation.js
- app/static/vendor/*

## Tool Development
Each tool MUST implement:
1. Blueprint: `bp = Blueprint('toolname', __name__)`
2. Summary API: `GET /api/<tool>/summary`
3. Health Check: `GET /api/<tool>/health`
4. Config Schema
5. Tests (unit + integration)

## Code Style
- Use Ruff for linting
- Use Black for formatting
- Type hints everywhere
- Docstrings (Google style)

## Forbidden
- NO CDNs (Tailwind, Google Fonts, etc.)
- NO external APIs without opt-in flag
- NO dark-mode toggles
- NO inline styles (use CSS classes)
- NO shared-core edits without Scope-Request
```

---

### 1.2 Gemini CLI einrichten

**Installation:**

```bash
# Install Gemini CLI
pip install google-generativeai

# Authentifizierung (API Key required)
export GEMINI_API_KEY="your-api-key-here"

# Alternative: gcloud auth (falls du Google Cloud nutzt)
gcloud auth application-default login
```

**Wrapper-Script für KUKANILEA:**

Erstelle `scripts/ai/gemini_cli.py`:

```python
#!/usr/bin/env python3
"""
KUKANILEA Gemini CLI Wrapper
Optimiert für Batch-Operations über alle 11 Worktrees.
"""

import os
import sys
import json
from pathlib import Path
import google.generativeai as genai

# Config
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# KUKANILEA-spezifische System-Prompt
KUKANILEA_CONTEXT = """
Du bist ein Code-Assistent für KUKANILEA, ein lokales Business-OS für Handwerksbetriebe.

ARCHITEKTUR:
- 11 Tools in isolierten Worktrees (siehe /Users/gensuminguyen/Kukanilea/worktrees/)
- Sovereign-11 Shell (White-Mode, 8pt-Grid, WCAG AA)
- Flask Blueprints (HMVC)
- Offline-First (keine CDNs, keine externen APIs)

CORE-REGELN:
1. Nie Shell-Assets editieren (layout.html, sidebar.html, fonts, icons)
2. Immer ToolInterface implementieren
3. Immer 8pt-Grid spacing (8, 16, 24, 32px)
4. Immer Tests schreiben
5. Scope-Request für Shared-Core-Änderungen

TOOLS (die 11):
1. Dashboard → /dashboard
2. Upload → /upload
3. Emailpostfach → /email
4. Messenger → /messenger
5. Kalender → /calendar
6. Aufgaben → /tasks
7. Zeiterfassung → /time
8. Projekte → /projects
9. Visualizer → /visualizer
10. Einstellungen → /settings
11. Chatbot → /chatbot (overlay)
"""

def ask_gemini(prompt: str, context_files: list = None) -> str:
    """Fragt Gemini mit KUKANILEA-Kontext."""
    
    # Baue vollständigen Prompt
    full_prompt = KUKANILEA_CONTEXT + "\n\n"
    
    # Lade Context-Files (falls angegeben)
    if context_files:
        for file_path in context_files:
            if Path(file_path).exists():
                with open(file_path, 'r') as f:
                    full_prompt += f"\n\n### FILE: {file_path}\n{f.read()}\n"
    
    full_prompt += f"\n\nUSER QUERY:\n{prompt}\n"
    
    # Frage Gemini
    response = model.generate_content(full_prompt)
    return response.text

def batch_ask(prompts: list, output_dir: str = None) -> dict:
    """Batch-Operation: Mehrere Prompts parallel."""
    
    results = {}
    for i, prompt in enumerate(prompts):
        print(f"[{i+1}/{len(prompts)}] Processing...")
        results[f"query_{i}"] = ask_gemini(prompt)
    
    # Speichere Results (optional)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        with open(f"{output_dir}/batch_results.json", 'w') as f:
            json.dump(results, f, indent=2)
    
    return results

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: gemini_cli.py <prompt>")
        sys.exit(1)
    
    prompt = ' '.join(sys.argv[1:])
    response = ask_gemini(prompt)
    print(response)
```

**Mache es ausführbar:**

```bash
chmod +x scripts/ai/gemini_cli.py
```

---

## 2. DIE 11 WORKTREES: STRUKTUR & OWNERSHIP

### 2.1 Übersicht

```
/Users/gensuminguyen/Kukanilea/
├── kukanilea_production/              (Core - Main Branch)
└── worktrees/
    ├── dashboard/                     → codex/dashboard
    ├── upload/                        → codex/upload
    ├── emailpostfach/                 → codex/emailpostfach
    ├── messenger/                     → codex/messenger
    ├── kalender/                      → codex/kalender
    ├── aufgaben/                      → codex/aufgaben
    ├── zeiterfassung/                 → codex/zeiterfassung
    ├── projekte/                      → codex/projekte
    ├── excel-docs-visualizer/         → codex/excel-docs-visualizer
    ├── einstellungen/                 → codex/einstellungen
    └── floating-widget-chatbot/       → codex/floating-widget-chatbot
```

### 2.2 Ownership-Matrix

| Tool | Worktree | Owned Paths | Forbidden Paths |
|------|----------|-------------|-----------------|
| **Core** | `kukanilea_production` | `app/templates/layout.html`, `app/static/{css,js,fonts,icons}/sovereign-*`, `app/web.py`, `app/core/*` | Domain-spezifische Blueprints |
| **Dashboard** | `worktrees/dashboard` | `app/modules/dashboard/*`, `app/templates/dashboard/*` | Shell-Assets, andere Module |
| **Upload** | `worktrees/upload` | `app/modules/upload/*`, `app/templates/upload/*` | Shell-Assets, andere Module |
| **Emailpostfach** | `worktrees/emailpostfach` | `app/modules/emailpostfach/*`, `app/templates/emailpostfach/*` | Shell-Assets, andere Module |
| **Messenger** | `worktrees/messenger` | `app/modules/messenger/*`, `app/templates/messenger/*` | Shell-Assets, andere Module |
| **Kalender** | `worktrees/kalender` | `app/modules/kalender/*`, `app/templates/kalender/*` | Shell-Assets, andere Module |
| **Aufgaben** | `worktrees/aufgaben` | `app/modules/aufgaben/*`, `app/templates/aufgaben/*` | Shell-Assets, andere Module |
| **Zeiterfassung** | `worktrees/zeiterfassung` | `app/modules/zeiterfassung/*`, `app/templates/zeiterfassung/*` | Shell-Assets, andere Module |
| **Projekte** | `worktrees/projekte` | `app/modules/projekte/*`, `app/templates/projekte/*` | Shell-Assets, andere Module |
| **Visualizer** | `worktrees/excel-docs-visualizer` | `app/modules/visualizer/*`, `app/templates/visualizer/*` | Shell-Assets, andere Module |
| **Einstellungen** | `worktrees/einstellungen` | `app/modules/einstellungen/*`, `app/templates/einstellungen/*` | Shell-Assets, andere Module |
| **Chatbot** | `worktrees/floating-widget-chatbot` | `app/modules/chatbot/*`, `app/templates/chatbot/*`, `app/static/js/chatbot.js` | Shell-Assets, andere Module |

---

## 3. WORKFLOW: PRO-WORKTREE-INTEGRATION

### 3.1 Standard-Workflow (für jedes Tool)

```bash
#!/bin/bash
# Standard-Workflow für ein Tool-Worktree

TOOL_NAME="dashboard"  # Ändere dies je nach Tool
WORKTREE_PATH="/Users/gensuminguyen/Kukanilea/worktrees/$TOOL_NAME"
CORE_PATH="/Users/gensuminguyen/Kukanilea/kukanilea_production"

# 1. Gehe ins Worktree
cd "$WORKTREE_PATH"

# 2. Stelle sicher, dass du auf dem richtigen Branch bist
git checkout codex/$TOOL_NAME

# 3. Pull latest changes
git pull origin codex/$TOOL_NAME

# 4. Starte Codex/Cursor mit Kontext
cursor . \
  --add "$CORE_PATH/docs/SOVEREIGN_11_FINAL_PACKAGE.md" \
  --add "$CORE_PATH/docs/TAB_OWNERSHIP_RULES.md" \
  --add "$CORE_PATH/contracts/CORE_TOOL_INTERFACE.md"

# 5. Nach Änderungen: Overlap-Check
cd "$CORE_PATH"
python scripts/dev/check_domain_overlap.py \
  --reiter "$TOOL_NAME" \
  --files "$(cd $WORKTREE_PATH && git diff --name-only main)" \
  --json

# 6. Wenn OK: Commit
cd "$WORKTREE_PATH"
git add -A
git commit -m "feat($TOOL_NAME): <beschreibung>"

# 7. Push
git push origin codex/$TOOL_NAME

# 8. Erstelle Pull Request (via GitHub UI)
```

### 3.2 Gemini CLI: Batch-Check für alle Worktrees

```bash
#!/bin/bash
# Batch-Check: Alle Worktrees auf Overlaps prüfen

WORKTREES=(
  "dashboard"
  "upload"
  "emailpostfach"
  "messenger"
  "kalender"
  "aufgaben"
  "zeiterfassung"
  "projekte"
  "excel-docs-visualizer"
  "einstellungen"
  "floating-widget-chatbot"
)

RESULTS_FILE="/tmp/overlap_results.json"
echo "{}" > "$RESULTS_FILE"

for tool in "${WORKTREES[@]}"; do
  echo "🔍 Checking $tool..."
  
  cd "/Users/gensuminguyen/Kukanilea/worktrees/$tool"
  
  # Overlap-Check
  overlap_result=$(python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py \
    --reiter "$tool" \
    --files "$(git diff --name-only main)" \
    --json)
  
  # Speichere Result
  echo "$overlap_result" | jq -r ".reiter = \"$tool\"" >> "$RESULTS_FILE"
  
  # Zeige Summary
  status=$(echo "$overlap_result" | jq -r '.status')
  if [ "$status" = "OK" ]; then
    echo "  ✅ $tool: OK"
  else
    echo "  ❌ $tool: VIOLATIONS"
  fi
done

echo ""
echo "📊 Full Report: $RESULTS_FILE"
cat "$RESULTS_FILE" | jq '.'
```

---

## 4. CODEX-PROMPTS: COPY-PASTE-READY

### 4.1 Neues Tool von Grund auf erstellen

**Prompt für Cursor Composer:**

```
Ich möchte ein neues KUKANILEA-Tool erstellen: [TOOL_NAME]

KONTEXT:
- KUKANILEA ist ein lokales Business-OS für Handwerker
- Sovereign-11 Shell (White-Mode, 8pt-Grid, WCAG AA)
- 11 Tools total, dieses ist Tool #[NUMBER]

ANFORDERUNGEN:
1. Implementiere ToolInterface (siehe contracts/CORE_TOOL_INTERFACE.md)
2. Erstelle Blueprint: app/modules/[tool]/
3. Erstelle Templates: app/templates/[tool]/
4. Implementiere APIs:
   - GET /api/[tool]/summary
   - GET /api/[tool]/health
5. Schreibe Tests: tests/domains/[tool]/
6. Nutze Shared-Services (app/core/services.py)
7. Folge 8pt-Grid spacing
8. WCAG AA Kontraste

FILES ZU ERSTELLEN:
- app/modules/[tool]/__init__.py
- app/modules/[tool]/routes.py
- app/modules/[tool]/models.py
- app/modules/[tool]/api.py
- app/templates/[tool]/index.html
- tests/domains/[tool]/test_integration.py

REFERENZEN:
- @docs/SOVEREIGN_11_FINAL_PACKAGE.md
- @contracts/CORE_TOOL_INTERFACE.md
- @app/modules/dashboard/ (als Beispiel)

STYLE:
- White-Mode forced
- 8pt-Grid (spacing: 8, 16, 24, 32px)
- Inter Font
- SVG Icons (from sprite.svg)
- HTMX für Navigation

Erstelle bitte die komplette Struktur für [TOOL_NAME].
```

### 4.2 Bestehende Komponente überarbeiten

**Prompt für Cursor Chat:**

```
Ich möchte [COMPONENT_NAME] in [TOOL_NAME] überarbeiten.

AKTUELLER STAND:
@app/modules/[tool]/[component].py

PROBLEME:
- [Problem 1]
- [Problem 2]

ZIEL:
- [Ziel 1]
- [Ziel 2]

ANFORDERUNGEN:
1. Behalte ToolInterface bei
2. Nutze SharedServices statt eigener Implementierung
3. Folge 8pt-Grid
4. WCAG AA Kontraste
5. Schreibe Tests

REFERENZEN:
- @docs/SOVEREIGN_11_FINAL_PACKAGE.md
- @app/core/services.py (SharedServices)

Bitte überarbeite die Komponente und zeige mir Before/After.
```

### 4.3 Overlap-Violations beheben

**Prompt für Cursor:**

```
Mein Overlap-Check zeigt Violations:

@scripts/dev/check_domain_overlap.py Output:
[PASTE OUTPUT HERE]

PROBLEM-FILES:
- app/templates/layout.html (CORE-OWNED)
- app/static/css/sovereign-shell.css (CORE-OWNED)

ICH MUSS:
Diese Änderungen in einen Scope-Request umwandeln.

REFERENZEN:
- @docs/SCOPE_REQUEST_TEMPLATE_V2.md
- @docs/scope_requests/SCOPE_REQUEST_EXAMPLE_DASHBOARD.md

Bitte:
1. Analysiere, welche Shell-Änderungen wirklich nötig sind
2. Erstelle einen Scope-Request (10 Sektionen)
3. Generiere Patch-File
4. Zeige mir die Alternative (falls Änderung nicht nötig)

Erstelle den Scope-Request für mich.
```

### 4.4 Integration-Test schreiben

**Prompt für Cursor:**

```
Ich brauche einen Integration-Test für [TOOL_NAME].

KONTEXT:
@app/modules/[tool]/

TEST-SZENARIEN:
1. Tool-Route lädt (200 OK)
2. API-Summary funktioniert
3. Health-Check grün
4. HTMX-Navigation kein Full-Reload
5. Empty-State zeigt bei keinen Daten

REFERENZEN:
- @tests/conftest.py (Shared Fixtures)
- @tests/domains/dashboard/test_integration.py (Beispiel)

ANFORDERUNGEN:
- pytest-Stil
- Nutze Shared-Fixtures
- Test-Coverage >90%
- Klar lesbar

Erstelle die komplette test_integration.py für [TOOL_NAME].
```

---

## 5. GEMINI CLI: BATCH-OPERATIONS

### 5.1 Batch: Alle Tools auf Compliance prüfen

**Script:** `scripts/ai/batch_compliance_check.py`

```python
#!/usr/bin/env python3
"""
Batch-Check: Alle 11 Tools auf KUKANILEA-Compliance prüfen.
Nutzt Gemini CLI.
"""

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from gemini_cli import ask_gemini, batch_ask

WORKTREES = [
    'dashboard', 'upload', 'emailpostfach', 'messenger', 'kalender',
    'aufgaben', 'zeiterfassung', 'projekte', 'excel-docs-visualizer',
    'einstellungen', 'floating-widget-chatbot'
]

COMPLIANCE_CHECKS = """
Prüfe dieses Tool auf KUKANILEA-Compliance:

CHECKS:
1. ToolInterface implementiert? (Blueprint, Summary-API, Health-Check)
2. 8pt-Grid spacing in CSS/Templates?
3. WCAG AA Kontraste?
4. Keine CDNs?
5. Keine Dark-Mode-Toggle?
6. Tests vorhanden (>70% coverage)?
7. Docstrings vorhanden?
8. Shared-Services genutzt (nicht dupliziert)?

OUTPUT FORMAT (JSON):
{{
  "tool": "toolname",
  "checks": {{
    "tool_interface": true/false,
    "grid_8pt": true/false,
    "wcag_aa": true/false,
    "no_cdn": true/false,
    "no_dark_mode": true/false,
    "tests": true/false,
    "docstrings": true/false,
    "shared_services": true/false
  }},
  "violations": ["list of violations"],
  "score": 0-100
}}
"""

def check_tool_compliance(tool_name: str) -> dict:
    """Prüft ein Tool auf Compliance."""
    
    worktree_path = f"/Users/gensuminguyen/Kukanilea/worktrees/{tool_name}"
    
    # Lade relevante Files
    context_files = [
        f"{worktree_path}/app/modules/{tool_name}/__init__.py",
        f"{worktree_path}/app/modules/{tool_name}/routes.py",
        f"{worktree_path}/app/templates/{tool_name}/index.html",
    ]
    
    # Filter existierende Files
    context_files = [f for f in context_files if Path(f).exists()]
    
    # Frage Gemini
    prompt = f"{COMPLIANCE_CHECKS}\n\nTOOL: {tool_name}\n"
    response = ask_gemini(prompt, context_files=context_files)
    
    return response

if __name__ == '__main__':
    print("🔍 KUKANILEA Compliance Check (all 11 tools)\n")
    
    results = {}
    
    for tool in WORKTREES:
        print(f"Checking {tool}...")
        results[tool] = check_tool_compliance(tool)
    
    # Zeige Summary
    print("\n📊 COMPLIANCE REPORT\n")
    for tool, result in results.items():
        print(f"{tool}:")
        print(f"  {result}\n")
    
    # Speichere Report
    import json
    with open('/tmp/compliance_report.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("Report saved: /tmp/compliance_report.json")
```

### 5.2 Batch: Code-Review für alle PRs

**Script:** `scripts/ai/batch_code_review.py`

```python
#!/usr/bin/env python3
"""
Batch-Code-Review: Alle offenen PRs reviewen mit Gemini.
"""

import os
import subprocess
from gemini_cli import ask_gemini

CODE_REVIEW_PROMPT = """
Reviewe diesen Pull Request für KUKANILEA:

KONTEXT:
- KUKANILEA: Lokales Business-OS für Handwerk
- Sovereign-11 Shell (White-Mode, 8pt-Grid, WCAG AA)
- Offline-First, keine CDNs

REVIEW-KRITERIEN:
1. ✅ Code-Qualität (Ruff-compliant, type hints, docstrings)
2. ✅ Tests vorhanden (>80% coverage)
3. ✅ Keine Shell-Violations (kein Edit an Core-Assets)
4. ✅ 8pt-Grid spacing
5. ✅ WCAG AA Kontraste
6. ✅ Keine externen Dependencies ohne Reason
7. ✅ Shared-Services genutzt (nicht dupliziert)
8. ✅ API-Contract eingehalten (Summary, Health)

OUTPUT FORMAT:
---
## Review Summary
- **Approve** / **Request Changes** / **Comment**

## Findings
### Critical Issues (must fix)
- [List]

### Suggestions (nice to have)
- [List]

### Praise (what's good)
- [List]

## Score: X/10
---

PR DIFF:
{diff}

Bitte reviewe diesen PR.
"""

def review_pr(pr_number: int) -> str:
    """Reviewt einen PR mit Gemini."""
    
    # Hole PR-Diff via GitHub CLI
    diff = subprocess.check_output(
        ['gh', 'pr', 'diff', str(pr_number)],
        text=True
    )
    
    # Frage Gemini
    prompt = CODE_REVIEW_PROMPT.format(diff=diff)
    review = ask_gemini(prompt)
    
    return review

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: batch_code_review.py <pr_number>")
        sys.exit(1)
    
    pr_number = int(sys.argv[1])
    review = review_pr(pr_number)
    
    print(review)
    
    # Optional: Poste Review direkt als GitHub Comment
    # subprocess.run(['gh', 'pr', 'comment', str(pr_number), '--body', review])
```

---

## 6. AUTOMATISIERUNG: SCRIPTS FÜR BEIDE CLIS

### 6.1 Codex: Auto-Fix Script

**Script:** `scripts/ai/codex_auto_fix.sh`

```bash
#!/bin/bash
# Auto-Fix häufige Probleme mit Codex

TOOL_NAME="$1"
WORKTREE_PATH="/Users/gensuminguyen/Kukanilea/worktrees/$TOOL_NAME"

if [ -z "$TOOL_NAME" ]; then
  echo "Usage: codex_auto_fix.sh <tool_name>"
  exit 1
fi

cd "$WORKTREE_PATH"

# 1. Ruff Auto-Fix
echo "🔧 Running Ruff auto-fix..."
ruff check --fix .

# 2. Black Formatting
echo "🎨 Running Black..."
black .

# 3. Type-Check (mypy)
echo "🔍 Type-checking..."
mypy app/modules/$TOOL_NAME/

# 4. Overlap-Check
echo "📊 Checking overlaps..."
python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py \
  --reiter "$TOOL_NAME" \
  --files "$(git diff --name-only main)" \
  --json

# 5. Cursor: Zeige Probleme
echo ""
echo "💡 Opening Cursor with problems..."
cursor . --goto-line 1

echo ""
echo "✅ Auto-fix complete. Review changes in Cursor."
```

### 6.2 Gemini: Batch-Documentation-Generator

**Script:** `scripts/ai/batch_generate_docs.py`

```python
#!/usr/bin/env python3
"""
Generiert automatisch Dokumentation für alle 11 Tools.
"""

from gemini_cli import ask_gemini
from pathlib import Path

WORKTREES = [
    'dashboard', 'upload', 'emailpostfach', 'messenger', 'kalender',
    'aufgaben', 'zeiterfassung', 'projekte', 'excel-docs-visualizer',
    'einstellungen', 'floating-widget-chatbot'
]

DOC_PROMPT = """
Erstelle eine User-Dokumentation für dieses KUKANILEA-Tool:

TOOL: {tool_name}

SOURCE CODE:
{source_code}

FORMAT (Markdown):
---
# {tool_name} – Benutzerhandbuch

## Übersicht
[Kurze Beschreibung: Was macht dieses Tool?]

## Funktionen
- [Feature 1]
- [Feature 2]
- [Feature 3]

## Anleitung
### 1. [Erste Funktion]
[Schritt-für-Schritt]

### 2. [Zweite Funktion]
[Schritt-für-Schritt]

## Tipps & Tricks
- [Tipp 1]
- [Tipp 2]

## Troubleshooting
**Problem:** [X]  
**Lösung:** [Y]
---

Bitte erstelle die Dokumentation.
"""

def generate_docs_for_tool(tool_name: str):
    """Generiert Docs für ein Tool."""
    
    worktree_path = f"/Users/gensuminguyen/Kukanilea/worktrees/{tool_name}"
    
    # Lade Source-Code
    source_files = [
        f"{worktree_path}/app/modules/{tool_name}/routes.py",
        f"{worktree_path}/app/modules/{tool_name}/models.py",
    ]
    
    source_code = ""
    for file in source_files:
        if Path(file).exists():
            with open(file, 'r') as f:
                source_code += f"\n### {Path(file).name}\n{f.read()}\n"
    
    # Frage Gemini
    prompt = DOC_PROMPT.format(
        tool_name=tool_name.title(),
        source_code=source_code
    )
    
    docs = ask_gemini(prompt)
    
    # Speichere Docs
    output_path = f"{worktree_path}/docs/user_guide.md"
    Path(output_path).parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(docs)
    
    print(f"✅ Docs generated: {output_path}")

if __name__ == '__main__':
    print("📚 Generating docs for all tools...\n")
    
    for tool in WORKTREES:
        print(f"Generating docs for {tool}...")
        generate_docs_for_tool(tool)
    
    print("\n✅ All docs generated!")
```

---

## 7. INTEGRATION-PIPELINE: STEP-BY-STEP

### 7.1 Die perfekte Integration eines Tools (mit beiden CLIs)

**Beispiel: Dashboard-Integration**

```bash
#!/bin/bash
# Komplette Integration: Dashboard

TOOL="dashboard"
WORKTREE="/Users/gensuminguyen/Kukanilea/worktrees/$TOOL"
CORE="/Users/gensuminguyen/Kukanilea/kukanilea_production"

echo "🚀 Starting integration of $TOOL"

# STEP 1: Codex – Code-Review
echo ""
echo "📝 STEP 1: Code-Review mit Codex"
cd "$WORKTREE"
cursor . --add "$CORE/docs/SOVEREIGN_11_FINAL_PACKAGE.md"

# Warte auf User-Bestätigung
read -p "Code reviewed? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 1
fi

# STEP 2: Auto-Fix mit Ruff/Black
echo ""
echo "🔧 STEP 2: Auto-Fix"
bash "$CORE/scripts/ai/codex_auto_fix.sh" "$TOOL"

# STEP 3: Overlap-Check
echo ""
echo "📊 STEP 3: Overlap-Check"
cd "$CORE"
python scripts/dev/check_domain_overlap.py \
  --reiter "$TOOL" \
  --files "$(cd $WORKTREE && git diff --name-only main)" \
  --json | tee /tmp/overlap_result.json

# Prüfe Result
status=$(cat /tmp/overlap_result.json | jq -r '.status')
if [ "$status" != "OK" ]; then
  echo "❌ Overlap violations found!"
  echo "Fix these or create Scope-Request."
  exit 1
fi

# STEP 4: Tests laufen lassen
echo ""
echo "🧪 STEP 4: Tests"
cd "$WORKTREE"
pytest -v

# STEP 5: Gemini – Compliance-Check
echo ""
echo "✅ STEP 5: Compliance-Check mit Gemini"
python "$CORE/scripts/ai/batch_compliance_check.py" | grep "$TOOL"

# STEP 6: Commit & Push
echo ""
echo "💾 STEP 6: Commit & Push"
cd "$WORKTREE"
git add -A
git commit -m "feat($TOOL): integration ready"
git push origin codex/$TOOL

# STEP 7: Create Pull Request
echo ""
echo "🔀 STEP 7: Create Pull Request"
gh pr create \
  --title "integrate: $TOOL shared-core changes" \
  --body "Integration von $TOOL gemäß Sovereign-11 Shell.\n\nOverlap-Check: ✅\nTests: ✅\nCompliance: ✅" \
  --base main \
  --head codex/$TOOL

echo ""
echo "✅ Integration complete! PR created."
```

### 7.2 Batch-Integration (alle Tools parallel)

**Script:** `scripts/integration/batch_integrate_all.sh`

```bash
#!/bin/bash
# Batch-Integration: Alle 11 Tools parallel

WORKTREES=(
  "dashboard"
  "upload"
  "emailpostfach"
  "messenger"
  "kalender"
  "aufgaben"
  "zeiterfassung"
  "projekte"
  "excel-docs-visualizer"
  "einstellungen"
  "floating-widget-chatbot"
)

CORE="/Users/gensuminguyen/Kukanilea/kukanilea_production"

# Parallel ausführen (maximal 3 gleichzeitig)
export -f integrate_tool
parallel -j 3 integrate_tool ::: "${WORKTREES[@]}"

function integrate_tool() {
  local tool="$1"
  local worktree="/Users/gensuminguyen/Kukanilea/worktrees/$tool"
  
  echo "🚀 [$tool] Starting integration..."
  
  # 1. Auto-Fix
  cd "$worktree"
  ruff check --fix . > /dev/null 2>&1
  black . > /dev/null 2>&1
  
  # 2. Overlap-Check
  cd "$CORE"
  overlap_result=$(python scripts/dev/check_domain_overlap.py \
    --reiter "$tool" \
    --files "$(cd $worktree && git diff --name-only main)" \
    --json)
  
  status=$(echo "$overlap_result" | jq -r '.status')
  
  if [ "$status" != "OK" ]; then
    echo "❌ [$tool] Overlap violations!"
    return 1
  fi
  
  # 3. Tests
  cd "$worktree"
  pytest -v > /dev/null 2>&1
  
  if [ $? -ne 0 ]; then
    echo "❌ [$tool] Tests failed!"
    return 1
  fi
  
  # 4. Commit & Push
  git add -A
  git commit -m "feat($tool): auto-integration" > /dev/null 2>&1
  git push origin codex/$tool > /dev/null 2>&1
  
  # 5. Create PR
  gh pr create \
    --title "integrate: $tool" \
    --body "Auto-integration via batch script" \
    --base main \
    --head codex/$tool > /dev/null 2>&1
  
  echo "✅ [$tool] Integration complete!"
}

echo ""
echo "✅ All integrations triggered!"
```

---

## 8. TROUBLESHOOTING & BEST PRACTICES

### 8.1 Häufige Probleme

#### Problem 1: Codex findet Kontext-Dateien nicht

**Symptom:** Cursor zeigt "File not found" für `@docs/...`

**Lösung:**

```bash
# Öffne Cursor vom Project-Root aus
cd /Users/gensuminguyen/Kukanilea/kukanilea_production
cursor .

# Füge Kontext-Dateien zum Workspace hinzu
# Cursor Settings → Workspace → Add Folder:
# - docs/
# - contracts/
# - app/
```

#### Problem 2: Gemini API Rate-Limit

**Symptom:** `429 Too Many Requests`

**Lösung:**

```python
# In gemini_cli.py: Füge Retry-Logic hinzu

import time
from google.api_core import retry

@retry.Retry(
    predicate=retry.if_exception_type(Exception),
    initial=1.0,
    maximum=10.0,
    multiplier=2.0,
    deadline=60.0
)
def ask_gemini(prompt: str) -> str:
    # ... existing code ...
    pass
```

#### Problem 3: Overlap-Violations trotz Scope-Request

**Symptom:** Overlap-Check meldet Violations, obwohl Scope-Request erstellt wurde

**Lösung:**

```bash
# Prüfe ob Scope-Request validiert wurde
cd /Users/gensuminguyen/Kukanilea/kukanilea_production
python scripts/integration/validate_scope_request.py \
  docs/scope_requests/my_request.md

# Wenn OK: Update Allowlist
python scripts/integration/update_allowlist.py \
  --add-from-scope-request docs/scope_requests/my_request.md
```

---

### 8.2 Best Practices

#### Codex/Cursor Best Practices

1. **Immer vom Project-Root starten**
   ```bash
   cd /Users/gensuminguyen/Kukanilea/kukanilea_production
   cursor .
   ```

2. **Kontext explizit laden**
   ```
   @docs/SOVEREIGN_11_FINAL_PACKAGE.md
   @contracts/CORE_TOOL_INTERFACE.md
   ```

3. **Multi-File-Edits nutzen** (Cursor Composer)
   - Cmd+K → Select multiple files → Edit all at once

4. **Custom Rules aktivieren**
   - Stelle sicher `.cursorrules` existiert im Root

5. **Git-Integration nutzen**
   - Cursor zeigt Git-Diff automatisch
   - Review vor Commit

#### Gemini CLI Best Practices

1. **Batch-Operations bevorzugen**
   - Schneller als 11× einzeln
   - Nutze `parallel` für echte Parallelisierung

2. **Kontext-Dateien immer mitgeben**
   ```python
   context_files=[
       "docs/SOVEREIGN_11_FINAL_PACKAGE.md",
       "app/modules/dashboard/__init__.py"
   ]
   ```

3. **Structured Output fordern**
   - JSON > Plain Text (leichter zu parsen)

4. **Caching nutzen** (falls Gemini unterstützt)
   - Spare API-Calls für gleiche Prompts

5. **Error-Handling**
   - Immer try/except um API-Calls
   - Retry bei 429/500 Errors

---

### 8.3 Cheat-Sheet: Quick Commands

```bash
# === CODEX ===

# 1. Starte Cursor mit Kontext
cursor /Users/gensuminguyen/Kukanilea/kukanilea_production \
  --add docs/SOVEREIGN_11_FINAL_PACKAGE.md

# 2. Auto-Fix für ein Tool
bash scripts/ai/codex_auto_fix.sh dashboard

# 3. Multi-File-Edit (Cursor Composer)
# Cmd+K → Select files → Type prompt → Apply


# === GEMINI CLI ===

# 1. Einzelne Frage
python scripts/ai/gemini_cli.py "Wie implementiere ich ToolInterface?"

# 2. Batch-Compliance-Check
python scripts/ai/batch_compliance_check.py

# 3. Batch-Docs-Generierung
python scripts/ai/batch_generate_docs.py

# 4. Code-Review für PR
python scripts/ai/batch_code_review.py 123


# === INTEGRATION ===

# 1. Tool integrieren (komplett)
bash scripts/integration/integrate_tool.sh dashboard

# 2. Alle Tools integrieren (parallel)
bash scripts/integration/batch_integrate_all.sh

# 3. Overlap-Check für alle
bash scripts/ai/batch_overlap_check.sh


# === TESTING ===

# 1. Tests für ein Tool
cd worktrees/dashboard && pytest -v

# 2. Tests für alle Tools
for d in worktrees/*; do
  (cd "$d" && pytest -v)
done

# 3. Healthcheck (Core)
cd kukanilea_production && ./scripts/ops/healthcheck.sh
```

---

## 📊 FINALE CHECKLISTE

### Vor dem Start:
- [ ] Codex/Cursor installiert
- [ ] Gemini CLI konfiguriert (`GEMINI_API_KEY`)
- [ ] Alle Scripts ausführbar (`chmod +x scripts/**/*.sh`)
- [ ] `.cursorrules` im Project-Root

### Für jedes Tool:
- [ ] Worktree existiert und ist aktuell (`git pull`)
- [ ] Cursor mit Kontext geöffnet
- [ ] ToolInterface implementiert
- [ ] Auto-Fix gelaufen (Ruff, Black)
- [ ] Overlap-Check grün
- [ ] Tests >80% Coverage
- [ ] Docs generiert (User-Guide)
- [ ] Compliance-Check bestanden
- [ ] PR erstellt & reviewed

### Nach Integration:
- [ ] Core-Healthcheck grün
- [ ] Alle 11 Routes → 200 OK
- [ ] Smoke-Test erfolgreich
- [ ] Dokumentation aktualisiert
- [ ] Team informiert

---

## 🎯 NEXT STEPS

1. **Setup:**
   ```bash
   # Installiere Tools
   brew install --cask cursor
   pip install google-generativeai
   
   # Konfiguriere
   export GEMINI_API_KEY="your-key"
   cd /Users/gensuminguyen/Kukanilea/kukanilea_production
   cursor .
   ```

2. **Teste mit einem Tool:**
   ```bash
   # Dashboard als Beispiel
   bash scripts/integration/integrate_tool.sh dashboard
   ```

3. **Skaliere auf alle Tools:**
   ```bash
   # Batch-Integration
   bash scripts/integration/batch_integrate_all.sh
   ```

---

**DU HAST JETZT ALLE TOOLS FÜR MAXIMALE PRODUKTIVITÄT! 🚀**

**Codex** für präzise Code-Edits im Kontext.  
**Gemini CLI** für Batch-Operations über alle Tools.  
**Automatisierung** für repetitive Tasks.  

**LET'S FUCKING SHIP IT! 💪🔥**
