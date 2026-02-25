import os
from pathlib import Path

def refactor_imports():
    # Use relative path from project root
    root = Path("app")
    if not root.exists():
        root = Path("Tophandwerk/kukanilea-git/app")
        
    replacements = {
        "import kukanilea_core_v3_fixed as legacy_core": "from app.core import logic as legacy_core",
        "import kukanilea_core_v3_fixed as core": "from app.core import logic as core",
        "import kukanilea_core_v3_fixed as _core": "from app.core import logic as _core",
        "import kukanilea_core_v3_fixed": "from app.core import logic",
        "app.ollama_runtime": "app.ollama",
        "from app import ollama_runtime": "from app import ollama",
        "from . import ollama_runtime": "from . import ollama"
    }
    
    count = 0
    for path in root.rglob("*.py"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        new_content = content
        for old, new in replacements.items():
            new_content = new_content.replace(old, new)
        
        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            count += 1
            print(f"  Refactored: {path}")
            
    print(f"[SUCCESS] Total files refactored: {count}")

if __name__ == "__main__":
    refactor_imports()
