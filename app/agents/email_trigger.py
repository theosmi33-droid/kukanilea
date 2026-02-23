"""
app/agents/email_trigger.py
Autonomer E-Mail Trigger für den Secretary Agenten.
Überwacht ein lokales oder konfiguriertes IMAP-Postfach und triggert Agenten-Aktionen.
"""

import imaplib
import email
import os
import asyncio
import logging
import secrets
import tempfile
from pathlib import Path
from email.header import decode_header
from typing import List, Tuple, Optional

from app.agents.orchestrator_v2 import delegate_task

logger = logging.getLogger("kukanilea.email_trigger")

class EmailTrigger:
    def __init__(self, interval_seconds: int = 300):
        self.interval = interval_seconds
        self.running = False
        self.task: Optional[asyncio.Task] = None
        # Konfiguration aus Umgebungsvariablen (Offline-first / Local priority)
        self.host = os.environ.get("KUKA_IMAP_HOST", "localhost")
        self.port = int(os.environ.get("KUKA_IMAP_PORT", "143"))
        self.user = os.environ.get("KUKA_IMAP_USER", "office@kukanilea.local")
        self.password = os.environ.get("KUKA_IMAP_PASSWORD", "secret")
        self.use_ssl = os.environ.get("KUKA_IMAP_SSL", "0") == "1"
        self.temp_dir = Path(tempfile.gettempdir()) / "kukanilea_email_attachments"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _wrap_with_salt(self, content: str) -> str:
        """Sicherheit: Salted Tags gegen Injection in E-Mail-Inhalten."""
        salt = secrets.token_hex(4)
        tag = f"KUKA_MAIL_{salt}"
        return f"
<{tag}>
{content}
</{tag}>
"

    async def start(self):
        if self.running:
            return
        self.running = True
        logger.info(f"IMAP Listener gestartet (Polling: {self.interval}s, Host: {self.host})")
        self.task = asyncio.create_task(self._loop())

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("IMAP Listener gestoppt.")

    async def _loop(self):
        while self.running:
            try:
                await self._check_emails()
            except Exception as e:
                logger.error(f"Fehler im IMAP Polling: {e}")
            await asyncio.sleep(self.interval)

    async def _check_emails(self):
        """Pollt das Postfach nach UNSEEN Mails."""
        try:
            if self.use_ssl:
                mail = imaplib.IMAP4_SSL(self.host, self.port)
            else:
                mail = imaplib.IMAP4(self.host, self.port)
            
            mail.login(self.user, self.password)
            mail.select("INBOX")
            
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK':
                return

            for num in messages[0].split():
                status, data = mail.fetch(num, '(RFC822)')
                if status != 'OK':
                    continue
                
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # E-Mail Metadaten extrahieren
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else "utf-8")
                
                from_ = msg.get("From")
                logger.info(f"Neue E-Mail von {from_}: {subject}")

                # Body und Anhänge extrahieren
                body, attachments = self._parse_message(msg)
                
                # Delegation an den Orchestrator
                prompt = (
                    f"EINGANGS-MAIL von: {from_}
"
                    f"BETREFF: {subject}
"
                    f"INHALT: {self._wrap_with_salt(body)}
"
                    f"ANHÄNGE: {', '.join(attachments) if attachments else 'Keine'}"
                )
                
                # Wir rufen delegate_task asynchron auf
                result = await delegate_task(prompt, tenant_id="SYSTEM_EMAIL", user_id="email_trigger")
                logger.info(f"Agent-Antwort auf Mail: {result}")

                # Mark as SEEN (standard imaplib behavior after fetch usually depends on server, 
                # but we implicitly mark or could use STORE +FLAGS \Seen)
                mail.store(num, '+FLAGS', '\Seen')

            mail.close()
            mail.logout()
        except Exception as e:
            logger.error(f"IMAP Verbindung fehlgeschlagen: {e}")

    def _parse_message(self, msg: email.message.Message) -> Tuple[str, List[str]]:
        body = ""
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body += payload.decode(errors="ignore")
                elif "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        # Sicherheit: PDF Filter
                        if filename.lower().endswith(".pdf"):
                            filepath = self.temp_dir / f"{secrets.token_hex(8)}_{filename}"
                            with open(filepath, "wb") as f:
                                f.write(part.get_payload(decode=True))
                            attachments.append(str(filepath))
                            logger.info(f"Anhang gespeichert: {filename}")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(errors="ignore")
                
        return body, attachments
