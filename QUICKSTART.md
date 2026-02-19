# KUKANILEA Quickstart (5 minutes)

## 1) Setup
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## 2) Optional local AI (Ollama)
```bash
ollama serve
ollama pull llama3.1:8b
```

## 3) Run app
```bash
python kukanilea_app.py
```
Open: [http://127.0.0.1:5051](http://127.0.0.1:5051)

Default dev login:
- `admin` / `admin`
