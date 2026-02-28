#!/bin/bash
# KUKANILEA UI/UX Hardening - White Mode & Variables
# Replaces hardcoded colors with CSS variables in templates.

TEMPLATES_DIR="/Users/gensuminguyen/Kukanilea/kukanilea_production/app/templates"

# 1. Replace White Text with main text variable
# Skip btn-primary and badges which should stay white
find "$TEMPLATES_DIR" -type f -name "*.html" -exec sed -i '' 's/color: #fff;/color: var(--color-text-main);/g' {} +
find "$TEMPLATES_DIR" -type f -name "*.html" -exec sed -i '' 's/color: #ffffff;/color: var(--color-text-main);/g' {} +

# 2. Fix specific cases where white IS needed (buttons)
find "$TEMPLATES_DIR" -type f -name "*.html" -exec sed -i '' 's/class="btn btn-primary" style="\(.*\)color: var(--color-text-main);/class="btn btn-primary" style="\1color: #fff;/g' {} +

# 3. Replace background colors with variables
find "$TEMPLATES_DIR" -type f -name "*.html" -exec sed -i '' 's/background: #0f1115;/background: var(--color-bg-root);/g' {} +
find "$TEMPLATES_DIR" -type f -name "*.html" -exec sed -i '' 's/background: #0f1115/background: var(--color-bg-root)/g' {} +

echo "UI Hardening complete."
