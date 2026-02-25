import requests
import re
from urllib.parse import quote_plus

def simulate_web_search(query):
    print(f"[START] Simuliere Suche für: '{query}'")
    url = f"https://duckduckgo.com/lite/?q={quote_plus(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        text = resp.text
        
        # Verbessertes Matching für DuckDuckGo Lite
        # Ergebnisse liegen oft in Tabellen oder einfachen Links
        matches = re.findall(r'class=\'result-link\' href=\'(.*?)\'>(.*?)</a>', text, re.DOTALL)
        
        if not matches:
            # Fallback Suche nach Links
            matches = re.findall(r'<a rel="nofollow" href="(.*?)">(.*?)</a>', text, re.DOTALL)

        if not matches:
            print("[WARNING] Keine Treffer via Regex.")
            return []
            
        print(f"[SUCCESS] {len(matches)} Ergebnisse gefunden.")
        for i, (link, title) in enumerate(matches[:3]):
            clean_title = re.sub('<[^<]+?>', '', title).strip()
            print(f"  {i+1}. {clean_title}")
        return matches
    except Exception as e:
        print(f"[ERROR] Fehler: {e}")
        return []

if __name__ == "__main__":
    simulate_web_search("aktuelle handwerker nachrichten")
