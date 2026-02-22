import os
import json
import logging
import requests
from pathlib import Path

logger = logging.getLogger("kukanilea.ai.diagnostics")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DIAGNOSTIC_MODEL = "llama3" # Default local model

class DiagnosticAgent:
    """
    Read-Only AI Diagnostic Agent for KUKANILEA.
    Analyzes logs and provides recovery suggestions.
    """
    
    def __init__(self, model=DIAGNOSTIC_MODEL):
        self.model = model

    def analyze_error(self, log_snippet: str):
        """Sends log data to local LLM for analysis."""
        
        prompt = f"""
        ### SYSTEM CONTEXT: KUKANILEA Business OS (Local-first, Python/Flask)
        ### TASK: Analyze the following error log and suggest a fix.
        ### CONSTRAINTS: Read-Only analysis. No filesystem mutation allowed.
        
        LOG SNIPPET:
        {log_snippet}
        
        INSTRUCTIONS:
        1. Identify the root cause.
        2. Suggest a specific technical fix.
        3. Note if this is a regression or security risk.
        
        OUTPUT FORMAT: Markdown.
        """
        
        try:
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            response.raise_for_status()
            analysis = response.json().get("response", "No analysis generated.")
            
            # AI Act Art. 50 Compliance: Transparency Labeling
            header = "> [!NOTE]\n> Diese Analyse wurde von einem lokalen KI-Modell erstellt.\n\n"
            return header + analysis
            
        except requests.RequestException as e:
            logger.error(f"Failed to connect to local LLM: {e}")
            return "AI Diagnostics unavailable: Local LLM service unreachable."

def run_cli_diagnostics(log_file_path):
    """Entry point for manual diagnostic audit."""
    path = Path(log_file_path).expanduser()
    if not path.exists():
        print(f"Log file not found: {path}")
        return

    # Read last 50 lines of logs
    with open(path, "r") as f:
        lines = f.readlines()
        snippet = "".join(lines[-50:])

    print(f"--- Analyzing last 50 lines of {path} ---")
    agent = DiagnosticAgent()
    print(agent.analyze_error(snippet))

if __name__ == "__main__":
    import sys
    log_file = sys.argv[1] if len(sys.argv) > 1 else "~/.kukanilea/logs/app.log"
    run_cli_diagnostics(log_file)
