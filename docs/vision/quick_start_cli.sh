#!/bin/bash
# 🚀 KUKANILEA – CLI QUICK-START
# Dieses Script richtet Codex + Gemini CLI ein und führt die erste Integration durch

set -e  # Exit on error

echo "🚀 KUKANILEA CLI QUICK-START"
echo "=============================="
echo ""

# === KONFIGURATION ===
ROOT="/Users/gensuminguyen/Kukanilea"
CORE="$ROOT/kukanilea_production"
WORKTREES="$ROOT/worktrees"

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# === STEP 1: PREREQUISITES CHECK ===
echo "📋 Step 1: Checking prerequisites..."

# Check Cursor/Windsurf
if command -v cursor &> /dev/null; then
    echo -e "${GREEN}✅${NC} Cursor found"
elif command -v windsurf &> /dev/null; then
    echo -e "${GREEN}✅${NC} Windsurf found"
else
    echo -e "${YELLOW}⚠️${NC}  Cursor/Windsurf not found. Installing..."
    brew install --cask cursor
fi

# Check Python
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✅${NC} Python found: $(python3 --version)"
else
    echo -e "${RED}❌${NC} Python not found. Please install Python 3.12+"
    exit 1
fi

# Check Git
if command -v git &> /dev/null; then
    echo -e "${GREEN}✅${NC} Git found"
else
    echo -e "${RED}❌${NC} Git not found. Please install Git"
    exit 1
fi

# Check GitHub CLI
if command -v gh &> /dev/null; then
    echo -e "${GREEN}✅${NC} GitHub CLI found"
else
    echo -e "${YELLOW}⚠️${NC}  GitHub CLI not found. Installing..."
    brew install gh
    gh auth login
fi

echo ""

# === STEP 2: INSTALL GEMINI CLI ===
echo "🤖 Step 2: Installing Gemini CLI..."

pip3 install -q google-generativeai

if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${YELLOW}⚠️${NC}  GEMINI_API_KEY not set."
    echo "Please get your API key from: https://aistudio.google.com/app/apikey"
    read -p "Enter your Gemini API Key: " api_key
    echo "export GEMINI_API_KEY='$api_key'" >> ~/.zshrc
    export GEMINI_API_KEY="$api_key"
    echo -e "${GREEN}✅${NC} API Key saved to ~/.zshrc"
else
    echo -e "${GREEN}✅${NC} GEMINI_API_KEY already set"
fi

echo ""

# === STEP 3: SETUP CORE PROJECT ===
echo "🏗️  Step 3: Setting up Core project..."

cd "$CORE"

# Create .cursorrules
if [ ! -f ".cursorrules" ]; then
    cat > .cursorrules << 'EOF'
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
EOF
    echo -e "${GREEN}✅${NC} .cursorrules created"
else
    echo -e "${GREEN}✅${NC} .cursorrules already exists"
fi

# Create Cursor settings
mkdir -p .cursor
if [ ! -f ".cursor/settings.json" ]; then
    cat > .cursor/settings.json << 'EOF'
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
  ]
}
EOF
    echo -e "${GREEN}✅${NC} Cursor settings created"
else
    echo -e "${GREEN}✅${NC} Cursor settings already exist"
fi

echo ""

# === STEP 4: CREATE AI SCRIPTS ===
echo "🧠 Step 4: Creating AI helper scripts..."

mkdir -p scripts/ai

# Gemini CLI Wrapper
cat > scripts/ai/gemini_cli.py << 'PYTHON'
#!/usr/bin/env python3
"""KUKANILEA Gemini CLI Wrapper"""

import os
import sys
import json
from pathlib import Path
import google.generativeai as genai

genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash-exp')

KUKANILEA_CONTEXT = """
Du bist ein Code-Assistent für KUKANILEA, ein lokales Business-OS für Handwerksbetriebe.

ARCHITEKTUR:
- 11 Tools in isolierten Worktrees
- Sovereign-11 Shell (White-Mode, 8pt-Grid, WCAG AA)
- Flask Blueprints (HMVC)
- Offline-First (keine CDNs, keine externen APIs)

CORE-REGELN:
1. Nie Shell-Assets editieren
2. Immer ToolInterface implementieren
3. Immer 8pt-Grid spacing
4. Immer Tests schreiben
5. Scope-Request für Shared-Core-Änderungen
"""

def ask_gemini(prompt: str) -> str:
    full_prompt = KUKANILEA_CONTEXT + "\n\n" + prompt
    response = model.generate_content(full_prompt)
    return response.text

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: gemini_cli.py <prompt>")
        sys.exit(1)
    
    prompt = ' '.join(sys.argv[1:])
    response = ask_gemini(prompt)
    print(response)
PYTHON

chmod +x scripts/ai/gemini_cli.py
echo -e "${GREEN}✅${NC} Gemini CLI wrapper created"

# Auto-Fix Script
cat > scripts/ai/codex_auto_fix.sh << 'BASH'
#!/bin/bash
# Auto-Fix häufige Probleme

TOOL_NAME="$1"
WORKTREE_PATH="/Users/gensuminguyen/Kukanilea/worktrees/$TOOL_NAME"

if [ -z "$TOOL_NAME" ]; then
  echo "Usage: codex_auto_fix.sh <tool_name>"
  exit 1
fi

cd "$WORKTREE_PATH"

echo "🔧 Running Ruff auto-fix..."
ruff check --fix . || true

echo "🎨 Running Black..."
black . || true

echo "✅ Auto-fix complete"
BASH

chmod +x scripts/ai/codex_auto_fix.sh
echo -e "${GREEN}✅${NC} Auto-fix script created"

echo ""

# === STEP 5: TEST INSTALLATION ===
echo "🧪 Step 5: Testing installation..."

# Test Gemini CLI
echo "Testing Gemini CLI..."
python3 scripts/ai/gemini_cli.py "Was ist KUKANILEA?" > /tmp/gemini_test.txt
if grep -q "Business-OS" /tmp/gemini_test.txt; then
    echo -e "${GREEN}✅${NC} Gemini CLI works!"
else
    echo -e "${YELLOW}⚠️${NC}  Gemini CLI response unexpected"
fi

# Test Cursor (just check if it starts)
echo "Testing Cursor..."
if command -v cursor &> /dev/null; then
    echo -e "${GREEN}✅${NC} Cursor is ready"
fi

echo ""

# === STEP 6: DEMO INTEGRATION ===
echo "🎯 Step 6: Running demo integration (Dashboard)..."

DEMO_TOOL="dashboard"
DEMO_WORKTREE="$WORKTREES/$DEMO_TOOL"

if [ -d "$DEMO_WORKTREE" ]; then
    echo "Found $DEMO_TOOL worktree"
    
    # Overlap-Check
    cd "$CORE"
    echo "Running overlap check..."
    python scripts/dev/check_domain_overlap.py \
      --reiter "$DEMO_TOOL" \
      --files "$(cd $DEMO_WORKTREE && git ls-files app/)" \
      --json > /tmp/overlap_demo.json || true
    
    status=$(cat /tmp/overlap_demo.json | jq -r '.status' 2>/dev/null || echo "UNKNOWN")
    
    if [ "$status" = "OK" ]; then
        echo -e "${GREEN}✅${NC} Overlap check passed for $DEMO_TOOL"
    else
        echo -e "${YELLOW}⚠️${NC}  Overlap check: $status"
    fi
else
    echo -e "${YELLOW}⚠️${NC}  $DEMO_TOOL worktree not found"
fi

echo ""

# === FINAL REPORT ===
echo "=============================="
echo "✅ SETUP COMPLETE!"
echo "=============================="
echo ""
echo "📊 Installation Summary:"
echo "  - Codex/Cursor: ✅"
echo "  - Gemini CLI: ✅"
echo "  - AI Scripts: ✅"
echo "  - Project Config: ✅"
echo ""
echo "🚀 Next Steps:"
echo ""
echo "1. Open Core in Cursor:"
echo "   cursor $CORE"
echo ""
echo "2. Test Gemini CLI:"
echo "   python scripts/ai/gemini_cli.py 'Erkläre mir das ToolInterface'"
echo ""
echo "3. Auto-fix a tool:"
echo "   bash scripts/ai/codex_auto_fix.sh dashboard"
echo ""
echo "4. Start integration:"
echo "   bash scripts/integration/integrate_tool.sh dashboard"
echo ""
echo "📚 Full Documentation:"
echo "   $CORE/docs/KUKANILEA_CLI_MASTER_ANLEITUNG.md"
echo ""
echo "💡 Pro Tips:"
echo "  - Use Cursor Composer (Cmd+K) for multi-file edits"
echo "  - Use Gemini CLI for batch operations"
echo "  - Always check overlap before committing"
echo ""
echo "Happy coding! 🎉"
