#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime
import os
from dataclasses import asdict, dataclass
from typing import Dict, List, Literal

import requests

Tone = Literal["freundlich", "neutral", "bestimmt", "streng"]
Length = Literal["kurz", "normal", "ausfuehrlich"]
Legal = Literal["none", "light", "strong"]
Goal = Literal["rabatt", "gutschrift", "ersatz", "nachbesserung", "ruecknahme"]
Recipient = Literal["haendler", "kunde", "behoerde", "versicherung"]
RewriteMode = Literal["off", "local", "ollama", "deepl_api"]


@dataclass
class MailOptions:
    tone: Tone = "neutral"
    length: Length = "normal"
    legal_level: Legal = "light"
    goal: Goal = "rabatt"
    recipient_type: Recipient = "haendler"
    language: str = "de"
    set_deadline: bool = False
    deadline_days: int = 7
    include_signature_block: bool = True
    rewrite_mode: RewriteMode = "local"  # local rules by default


@dataclass
class MailInput:
    context: str
    facts: Dict[str, str]  # e.g. {"lieferdatum":"30.01.2026","lieferschein":"...","kunde":"..."}
    attachments: List[str]
    sender_name: str = "Peter Nguyen"
    sender_company: str = "FLISA-Bau"
    sender_email: str = "kontakt@flisa.de"
    sender_phone: str = "030 488 27 840"
    sender_mobile: str = "0173 987 13 71"
    recipient_name: str = ""
    recipient_company: str = ""
    draft: str = ""  # optional existing draft to rewrite


class MailAgent:
    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.ollama_model = os.getenv("KUKANILEA_OLLAMA_MODEL", "llama3.1")

        # Optional: DeepL API (only if you have a key)
        self.deepl_api_key = os.getenv("DEEPL_API_KEY", "")
        self.deepl_api_url = os.getenv("DEEPL_API_URL", "https://api-free.deepl.com/v2/translate")

    def _deadline_text(self, opt: MailOptions) -> str:
        if not opt.set_deadline:
            return ""
        target_date = (datetime.date.today() + datetime.timedelta(days=opt.deadline_days)).strftime(
            "%d.%m.%Y"
        )
        if opt.legal_level == "strong":
            return f"\nBitte teilen Sie uns bis spätestens {target_date} mit, wie die Regulierung erfolgt.\n"
        return f"\nÜber eine Rückmeldung bis {target_date} würden wir uns freuen.\n"

    def _goal_text(self, opt: MailOptions) -> str:
        mapping = {
            "rabatt": "einen Rabatt bzw. eine Gutschrift",
            "gutschrift": "eine Gutschrift",
            "ersatz": "eine Ersatzlieferung",
            "nachbesserung": "eine Nachbesserung",
            "ruecknahme": "eine Rücknahme der defekten Ware",
        }
        return mapping.get(opt.goal, "eine Regulierung")

    def _tone_opening(self, opt: MailOptions) -> str:
        if opt.tone == "freundlich":
            return "Guten Tag,\n\n"
        if opt.tone == "neutral":
            return "Sehr geehrte Damen und Herren,\n\n"
        if opt.tone == "bestimmt":
            return "Guten Tag,\n\n"
        if opt.tone == "streng":
            return "Sehr geehrte Damen und Herren,\n\n"
        return "Guten Tag,\n\n"

    def _subject(self, inp: MailInput, opt: MailOptions) -> str:
        base = "Mangelanzeige – defekte Fliesenlieferung"
        goal = opt.goal.replace("_", " ")
        if opt.goal in ("rabatt", "gutschrift"):
            return f"{base} / Bitte um {goal}"
        return f"{base} / Bitte um {goal}"

    def _body(self, inp: MailInput, opt: MailOptions) -> str:
        opening = self._tone_opening(opt)

        # Facts block (no inventions)
        facts_lines = []
        if inp.facts.get("lieferdatum"):
            facts_lines.append(f"Lieferdatum: {inp.facts['lieferdatum']}")
        if inp.facts.get("lieferschein"):
            facts_lines.append(f"Lieferschein: {inp.facts['lieferschein']}")
        if inp.facts.get("rechnung"):
            facts_lines.append(f"Rechnung: {inp.facts['rechnung']}")
        if inp.facts.get("projekt"):
            facts_lines.append(f"Projekt: {inp.facts['projekt']}")
        facts_section = ""
        if facts_lines and opt.length != "kurz":
            facts_section = "Bezug:\n" + "\n".join(f"- {line}" for line in facts_lines) + "\n\n"

        # Main message
        main = "bei der gelieferten Ware wurde ein Mangel festgestellt. Mehrere Fliesen weisen sichtbare Beschädigungen auf.\n"
        if opt.length == "ausfuehrlich":
            main += "Der Mangel wurde beim Auspacken/Verarbeiten erkannt. Zur Dokumentation sind Fotos beigefügt.\n"

        attachments_hint = ""
        if inp.attachments:
            attachments_hint = "Fotos zur Dokumentation sind im Anhang beigefügt.\n"
        else:
            attachments_hint = "Fotos zur Dokumentation folgen / liegen vor.\n"

        ask = f"Bitte prüfen Sie den Sachverhalt und schlagen Sie eine Regulierung in Form von {self._goal_text(opt)} vor.\n"
        deadline = self._deadline_text(opt)

        closing = ""
        if opt.tone in ("bestimmt", "streng") and opt.legal_level in ("light", "strong"):
            closing += "Vielen Dank für die zeitnahe Bearbeitung.\n"
        else:
            closing += "Vielen Dank.\n"

        signature = ""
        if opt.include_signature_block:
            signature = (
                "\nMit freundlichen Grüßen\n\n"
                f"{inp.sender_name}\n"
                f"{inp.sender_company}\n"
                f"Tel.: {inp.sender_phone}\n"
                f"Mobil: {inp.sender_mobile}\n"
                f"E-Mail: {inp.sender_email}\n"
            )

        # Assemble
        body = (
            opening
            + facts_section
            + main
            + attachments_hint
            + ask
            + deadline
            + "\n"
            + closing
            + signature
        )
        return body

    def _local_rewrite(self, text: str, opt: MailOptions) -> str:
        # Simple local “DeepL-Write-like” rules: remove fluff, normalize whitespace, keep meaning.
        t = text.replace("\r\n", "\n")
        while "\n\n\n" in t:
            t = t.replace("\n\n\n", "\n\n")
        # Make wording a bit tighter
        t = t.replace(
            "Wir bitten Sie um Prüfung des Sachverhalts", "Bitte prüfen Sie den Sachverhalt"
        )
        t = t.replace("Wir bitten Sie um", "Bitte")
        return t.strip() + "\n"

    def _ollama_rewrite(self, text: str, opt: MailOptions) -> str:
        prompt = (
            "Du bist ein professioneller deutscher E-Mail-Redakteur.\n"
            "Aufgabe: Formuliere den folgenden E-Mail-Entwurf stilistisch besser (klar, höflich, präzise), "
            "OHNE Fakten zu erfinden oder Inhalte zu ändern.\n"
            f"Ton: {opt.tone}. Länge: {opt.length}. Rechtlich: {opt.legal_level}.\n\n"
            "Entwurf:\n---\n"
            f"{text}\n---\n"
            "Gib nur den finalen E-Mail-Text zurück."
        )
        r = requests.post(
            f"{self.ollama_host}/api/generate",
            json={"model": self.ollama_model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        r.raise_for_status()
        return (r.json().get("response") or "").strip() + "\n"

    def _deepl_api_rewrite(self, text: str) -> str:
        # NOTE: DeepL API is primarily translation. Some accounts/products provide formal/informal & tone controls,
        # but “Write” is not guaranteed via this endpoint. We keep it optional and safe.
        if not self.deepl_api_key:
            return text
        payload = {
            "auth_key": self.deepl_api_key,
            "text": text,
            "target_lang": "DE",
        }
        r = requests.post(self.deepl_api_url, data=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        translations = data.get("translations", [])
        if translations:
            return translations[0].get("text", text)
        return text

    def generate(self, inp: MailInput, opt: MailOptions) -> Dict[str, object]:
        subject = self._subject(inp, opt)
        base_body = self._body(inp, opt)

        # Rewrite options
        if opt.rewrite_mode == "local":
            body = self._local_rewrite(base_body, opt)
        elif opt.rewrite_mode == "ollama":
            body = self._ollama_rewrite(base_body, opt)
        elif opt.rewrite_mode == "deepl_api":
            body = self._deepl_api_rewrite(base_body)
        else:
            body = base_body

        checklist = []
        if inp.attachments:
            checklist.append(f"Anhänge geprüft: {len(inp.attachments)} Datei(en) angehängt")
        else:
            checklist.append("Anhänge fehlen: Fotos anhängen")

        if opt.set_deadline:
            checklist.append(f"Frist gesetzt: {opt.deadline_days} Tage")
        if not inp.facts:
            checklist.append("Fakten fehlen: Lieferschein/Rechnung/Datum ergänzen")
        return {
            "subject": subject,
            "body": body,
            "checklist": checklist,
            "options": asdict(opt),
        }


if __name__ == "__main__":
    # Demo with your current case:
    agent = MailAgent()
    inp = MailInput(
        context="Mangel defekte Fliesenlieferung, Fotos per Mail an Händler, Rabatt anfragen",
        facts={"lieferdatum": "30.01.2026"},
        attachments=[
            "14d488d7-cf8f-48a2-a6b5-c91979da3adb.jpg",
            "93fa3e12-ed8c-46de-85db-334b5c517b68.jpg",
        ],
    )
    opt = MailOptions(
        tone="neutral", length="normal", legal_level="light", goal="rabatt", rewrite_mode="ollama"
    )
    out = agent.generate(inp, opt)
    print("BETREFF:", out["subject"])
    print("\nTEXT:\n", out["body"])
    print("\nCHECKLISTE:", out["checklist"])
