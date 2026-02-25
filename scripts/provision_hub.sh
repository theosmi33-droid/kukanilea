#!/bin/bash
# KUKANILEA Hub Provisioning Script
# Focus: Security, Performance, and Hardware-Adaptive AI (llmfit)

set -e

echo "Starting KUKANILEA Hub Provisioning..."

# 1. Install llmfit (Hardware Intelligence)
if ! command -v llmfit &> /dev/null; then
    echo "Installing llmfit..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: via Homebrew tap
        if command -v brew &> /dev/null; then
            brew tap alexsjones/homebrew-tap
            brew install llmfit
        else
            echo "Homebrew missing. Downloading binary directly..."
            # Placeholder for direct binary download if brew is missing
        fi
    else
        # Linux / ZimaBlade (Debian/Ubuntu)
        echo "Installing for Linux..."
        # Example using curl to get the latest release binary from GitHub
        # curl -L https://github.com/AlexsJones/llmfit/releases/latest/download/llmfit_linux_amd64 -o /usr/local/bin/llmfit
        # chmod +x /usr/local/bin/llmfit
    fi
fi

# 2. Verify Installation
if command -v llmfit &> /dev/null; then
    echo "[SUCCESS] llmfit installed: $(llmfit version)"
    llmfit system
else
    echo "[WARNING] llmfit could not be installed. KUKANILEA will use safe defaults."
fi

# 3. Setup Ollama
if ! command -v ollama &> /dev/null; then
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

echo "Provisioning complete."
