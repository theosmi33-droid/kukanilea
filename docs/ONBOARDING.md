# Onboarding

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
python scripts/seed_dev_users.py
python kukanilea_app.py
```

Open: http://127.0.0.1:5051

## Update Button
```bash
./update.sh
```

## Common Errors
- **Login fails**: run `python scripts/seed_dev_users.py`.
- **Missing OCR**: install tesseract/poppler locally.
