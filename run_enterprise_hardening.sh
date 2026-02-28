#!/bin/bash
set -e

echo "🚀 Starting Enterprise Hardening..."

echo "1. Ensuring strict architecture normalization..."
mkdir -p app/{core,agents,services,web,ui,security}

echo "2. Validating entry point..."
if [ ! -f "kukanilea_app.py" ]; then
    echo "Entry point missing!"
    exit 1
fi

echo "3. Removing legacy file patterns..."
find . -type f -name "*_v3_fixed*" -o -name "*_FIXED*" -o -name "*legacy*" | xargs rm -f 2>/dev/null || true

echo "4. Running Ruff checks..."
.venv/bin/pip install ruff > /dev/null
.venv/bin/ruff check . --fix > /dev/null || true

echo "5. Compiling Python files..."
python3 -m compileall . > /dev/null

echo "6. Benchmarking Startup..."
START=$(date +%s%3N)
PYTHONPATH=. .venv/bin/python kukanilea_app.py --version > /dev/null
END=$(date +%s%3N)
ELAPSED=$((END-START))
echo "Startup time: ${ELAPSED}ms"
if [ $ELAPSED -gt 2000 ]; then
    echo "⚠️ Warning: Startup > 2s (${ELAPSED}ms)"
fi

echo "✅ Hardening routine completed."
