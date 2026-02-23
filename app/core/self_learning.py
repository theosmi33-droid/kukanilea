import os
import json
import secrets
from datetime import datetime
from pathlib import Path
from sqlalchemy import text
from app.models.rule import get_sa_session, RuleProposal

# Kukanilea Self Learning System
IDENTITY_DIR = Path("instance/identity")
LESSONS_FILE = IDENTITY_DIR / "lessons.md"

def log_correction(user_input: str, agent_context: str):
    """
    Jede manuelle Korrektur eines Nutzers wird als Rohtext in lessons.md protokolliert.
    Format: Zeitstempel, Agenten-Kontext, Nutzerkorrektur.
    """
    if not IDENTITY_DIR.exists():
        IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\\n### Korrektur {timestamp}\\nKONTEXT: {agent_context}\\nNUTZER-FEEDBACK: {user_input}\\n---\\n"
    
    with open(LESSONS_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    return True

def wrap_rule_with_salt(rule_text: str) -> str:
    """
    Wickelt eine Regel in Salted Sequence Tags ein, um Cross-Prompting zu verhindern.
    """
    salt = secrets.token_hex(4)
    tag = f"KUKA_SALT_{salt}"
    return f"\\n<{tag}>\\n{rule_text}\\n</{tag}>\\n"

def hybrid_check(action_data: dict) -> bool:
    """
    Python-basierte Vorprüfung für Standard-Limits (Hybrid Observer).
    Verhindert riskante Aktionen ohne LLM-Overhead.
    """
    amount = action_data.get("amount", 0)
    # Kritische Grenze: Alles über 1000€ muss manuell geprüft werden
    if amount > 1000:
        return False # Nicht freigegeben
    
    # Weitere statische Regeln können hier ergänzt werden
    return True

async def propose_rule():
    """
    Asynchrone Auswertung der gesammelten lessons.md-Einträge.
    Ein LLM generiert aus wiederkehrenden Korrekturmustern einen neuen Regelentwurf.
    """
    if not LESSONS_FILE.exists():
        return None

    lessons_content = LESSONS_FILE.read_text(encoding="utf-8")
    if not lessons_content.strip():
        return None

    # LLM-Aufruf über app.agents.orchestrator (Simuliert)
    # In der echten Implementierung würde hier der Orchestrator gerufen werden.
    from app.agents.orchestrator import answer as agent_answer
    
    prompt = (
        "Du bist der Kukanilea Observer. Analysiere das Nutzerfeedback in den folgenden Lektionen. "
        "Erstelle eine neue, präzise Regel für das PLAYBOOK im JSON Format.\\n\\n"
        f"LEKTIONEN:\\n{lessons_content}\\n\\n"
        "Antworte NUR mit validem JSON, das 'rule_text' und 'reason' enthält."
    )
    
    try:
        # result = agent_answer(prompt, role="OBSERVER")
        # dummy logic for now as it's a prototype
        proposal_data = {
            "rule_text": "max_order_amount: 500",
            "reason": "Wiederholte Korrektur bei hohen Bestellsummen am 23.02."
        }
        
        # In DB speichern
        session = get_sa_session()
        new_proposal = RuleProposal(
            rule_text=proposal_data["rule_text"],
            reason=proposal_data["reason"],
            status='pending'
        )
        session.add(new_proposal)
        session.commit()
        proposal_id = new_proposal.id
        session.close()
        
        return proposal_id
    except Exception as e:
        print(f"Fehler bei Rule-Proposal: {e}")
        return None

def apply_approved_rule_to_playbook(proposal_id: int):
    """
    Schreibt eine freigegebene Regel sicher in das PLAYBOOK.md.
    Nutzt Salted Tags beim Schreibvorgang.
    """
    session = get_sa_session()
    proposal = session.query(RuleProposal).filter_by(id=proposal_id, status='pending').first()
    
    if proposal:
        playbook_path = IDENTITY_DIR / "PLAYBOOK.md"
        salted_rule = wrap_rule_with_salt(proposal.rule_text)
        
        with open(playbook_path, "a", encoding="utf-8") as f:
            f.write(salted_rule)
        
        proposal.status = 'approved'
        proposal.reviewed_at = datetime.utcnow()
        session.commit()
        session.close()
        return True
    
    session.close()
    return False
