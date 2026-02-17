# KUKANILEA Quick Reference

## Local setup (macOS/Linux)
```bash
git clone https://github.com/theosmi33-droid/kukanilea.git
cd kukanilea
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
python scripts/seed_dev_users.py
python kukanilea_app.py
```

## OCR prerequisites
```bash
# macOS
brew install tesseract tesseract-lang

# Linux (example)
sudo apt install tesseract-ocr tesseract-ocr-deu
```

## Quality gates
```bash
python -m compileall -q .
ruff check . --fix
ruff format .
pytest -q
python -m app.devtools.triage --ci --fail-on-warnings \
  --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
```
