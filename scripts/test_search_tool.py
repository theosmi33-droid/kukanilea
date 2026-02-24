
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.agents.tools import _web_search_handler, WebSearchArgs

def test_search():
    print("🚀 Teste Web-Suche (DuckDuckGo Lite)...")
    args = WebSearchArgs(query="aktuelle benzinpreise deutschland")
    result = _web_search_handler(tenant_id="test", user="tester", args=args)
    
    if "error" in result:
        print(f"❌ Fehler: {result['error']}")
    else:
        print(f"✅ Suche erfolgreich für: {result['query']}")
        for i, res in enumerate(result.get("results", [])[:3]):
            print(f"  {i+1}. {res['title']}")
            
if __name__ == "__main__":
    test_search()
