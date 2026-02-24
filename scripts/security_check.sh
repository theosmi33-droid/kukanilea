#!/bin/bash
# scripts/security_check.sh
# Pre-Commit Hook zum Scannen nach versehentlich committeten Secrets.

set -e

echo "🔒 Starte Security-Check nach hardcoded Secrets..."

# Wir nutzen trufflehog3 oder detect-secrets, falls installiert
if command -v trufflehog &> /dev/null; then
    echo "Trufflehog gefunden. Scanne Repository..."
    trufflehog filesystem . --exclude-paths .gitignore --fail
elif command -v detect-secrets &> /dev/null; then
    echo "detect-secrets gefunden. Scanne Repository..."
    detect-secrets scan --baseline .secrets.baseline
else
    echo "⚠️ Weder Trufflehog noch detect-secrets installiert."
    echo "Bitte installiere eines der Tools (z.B. 'pip install detect-secrets' oder 'brew install trufflehog')."
    echo "Wir überspringen den automatischen Scan für jetzt."
fi

# Einfacher manueller Grep als Fallback für die offensichtlichsten Fehler
echo "Scanne nach 'password =' im Code..."
if grep -rin "password[ ]*=[ ]*["'][^"']*["']" app/ | grep -v "test"; then
    echo "❌ KRITISCH: Mögliches hardcoded Passwort gefunden!"
    exit 1
fi

echo "✅ Security-Check bestanden."
exit 0
