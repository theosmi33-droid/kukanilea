"""
app/core/identity_parser.py
Parser für den OpenClaw Blueprint.
Wandelt Markdown-Identitätsdateien in Agenten-Instruktionen um.
"""

import os
from pathlib import Path
import shutil

class IdentityParser:
    def __init__(self, identity_dir: Path):
        self.identity_dir = identity_dir
        self.ensure_identity_exists()

    def ensure_identity_exists(self):
        """Stellt sicher, dass die Identitätsdateien im instance Ordner liegen."""
        self.identity_dir.mkdir(parents=True, exist_ok=True)
        template_dir = Path(__file__).parent.parent / "templates" / "identity"
        
        files = ["SOUL.md", "PLAYBOOK.md", "BOUNDARIES.md", "lessons.md"]
        for f in files:
            target = self.identity_dir / f
            if not target.exists():
                source = template_dir / f
                if source.exists():
                    shutil.copy(source, target)

    def load_file_content(self, filename: str) -> str:
        path = self.identity_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def wrap_rule_with_salt(self, rule_text: str) -> str:
        """
        Wickelt eine Regel in Salted Sequence Tags ein, um Cross-Prompting zu verhindern.
        """
        import secrets
        salt = secrets.token_hex(4)
        tag = f"KUKA_SALT_{salt}"
        return f"\n<{tag}>\n{rule_text}\n</{tag}>\n"

    def get_master_instructions(self) -> str:
        """Kombiniert Soul, Playbook und Lessons für den Master-Agenten."""
        soul = self.load_file_content("SOUL.md")
        playbook = self.load_file_content("PLAYBOOK.md")
        lessons = self.load_file_content("lessons.md")
        
        # Injection-Schutz: Wickle das Playbook in Salted Tags ein
        salted_playbook = self.wrap_rule_with_salt(playbook)
        
        return f"{soul}\n\n## Deine Regeln (PLAYBOOK):\n{salted_playbook}\n\n## Erlernte Lektionen:\n{lessons}"

    def get_boundaries(self) -> str:
        return self.load_file_content("BOUNDARIES.md")

    def append_lesson(self, lesson_text: str, context: str = "GENERIC"):
        """Fügt eine neue Lektion an lessons.md an über das Self-Learning System."""
        from app.core.self_learning import log_correction
        log_correction(lesson_text, context)
