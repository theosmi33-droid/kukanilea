#!/bin/bash
# scripts/tests/run_loadtest.sh
# Runs Locust load test against the local KUKANILEA instance.

set -e

# Base Path setup
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../" && pwd)"

LOCUST_FILE="$SCRIPT_DIR/locustfile.py"
HOST="http://127.0.0.1:5051"
USERS=10
SPAWN_RATE=2
DURATION="60s"

echo "🚀 Starting Load Test against $HOST..."
echo "Config: $USERS users, $SPAWN_RATE spawn rate, duration $DURATION"

locust -f "$LOCUST_FILE"
    --host "$HOST"
    --users "$USERS"
    --spawn-rate "$SPAWN_RATE"
    --run-time "$DURATION"
    --headless
    --only-summary

echo "✅ Load Test Complete."
