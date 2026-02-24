#!/bin/bash
# KUKANILEA Performance Verifier (Robust Version)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOCUST_BIN="$PROJECT_ROOT/.venv/bin/locust"

TARGET_URL=${1:-"http://127.0.0.1:5051"}
USERS=10
SPAWN_RATE=2
DURATION="5m"
REPORT_DIR="$PROJECT_ROOT/reports/load_test_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$REPORT_DIR"

echo "🚀 Starte KUKANILEA Load-Test gegen $TARGET_URL"
echo "👥 User: $USERS | Rate: $SPAWN_RATE | Dauer: $DURATION"

# Locust im Headless-Mode starten
"$LOCUST_BIN" -f "$PROJECT_ROOT/tests/load/test_baseline.py" \
    --host "$TARGET_URL" \
    --users "$USERS" \
    --spawn-rate "$SPAWN_RATE" \
    --run-time "$DURATION" \
    --headless \
    --csv="$REPORT_DIR/results" \
    --html="$REPORT_DIR/report.html"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Load-Test erfolgreich abgeschlossen."
    echo "📊 Ergebnisse in $REPORT_DIR"
    echo "------------------------------------------------"
    tail -n +2 "$REPORT_DIR/results_stats.csv" | awk -F',' '{print $1 ": Median "$10"ms, P95 "$16"ms"}'
    echo "------------------------------------------------"
else
    echo "❌ Load-Test fehlgeschlagen oder Performance-Budget überschritten!"
fi

exit $EXIT_CODE
