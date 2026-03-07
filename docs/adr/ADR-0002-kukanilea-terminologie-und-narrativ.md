# ADR-0002: KUKANILEA Terminologie und Narrativ

- Status: Accepted
- Date: 2026-03-06
- Related: docs/agents/AGENTS.md, app/agents/config/AGENTS.md

## Kontext
In produktiver Doku, produktiven UI-Texten und MIA-Narrativen waren noch Fremdframings und Fremdprodukt-Begriffe enthalten (z. B. OpenClaw, externe Assistenten-Namen, Zero-CDN als Primärbegriff).

Das erschwert eine kohärente Produktnarration und verwässert die Identität von KUKANILEA.

## Entscheidung
Ab sofort gilt für produktive Kommunikation und produktive Konfiguration:

1. Primäre Plattformbezeichnung ist **KUKANILEA**.
2. Für den lokalen Ausführungspfad wird **Sovereign-11** verwendet.
3. Der agentische Kern wird als **MIA** bezeichnet.
4. Architekturprinzipien werden als **local-first** und **offline-first** benannt.
5. Sicherheits- und Compliance-Qualität wird als **auditierbar** benannt.

## Regeln für Fremdbezüge
- Fremdbezüge sind nur zulässig, wenn sie für **historischen Kontext** oder **technische Kompatibilität** zwingend notwendig sind.
- Solche Bezüge müssen klar als Kontext markiert sein und dürfen nicht das Primärnarrativ dominieren.

## Konsequenzen
- Produktive UI-Texte, Agenten-Dokumentation und Kernstatus-Doku sprechen mit einer einheitlichen KUKANILEA-Sprache.
- MIA-Narrative sind konsistent mit Sovereign-11, local-first, offline-first und auditierbar.
- Künftige Doku- und Textänderungen werden gegen diese Terminologie geprüft.
