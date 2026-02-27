# KUKANILEA Fleet Configuration (OpenClaw Architecture)

Das System basiert auf einer hochgradig parallelen Agenten-Flotte mit asynchronem Task-Routing.

## 1. Orchestrators (Die Dirigenten)
Zuständig für Triage, Tool-Auswahl und Context-Window-Management.
1. **Main Orchestrator**: Nimmt User-Requests entgegen, zerlegt sie in Teilaufgaben (Sub-Tasks).
2. **Review Orchestrator**: Validiert die Outputs der Worker gegen die SOUL-Directives, führt Quality Gates durch.
3. **Security Orchestrator**: Kapselt Inputs (Prompt Injection Defense), führt Red-Teaming gegen Outputs durch.

## 2. Workers (Die Spezialisten)
- W01: OCR & Vision
- W02: Document Extraction (PDF, Office)
- W03: RAG Ingestion & Embedding
- W04: RAG Retrieval (Vector + FTS)
- W05: Internet Search (Tavily/LangGraph)
- W06: Email Processing (IMAP/SMTP)
- W07: Time Tracking & Controlling
- W08: Contact Management (CRM)
- W09: ERP Sync (Lexware/Tophandwerk)
- W10: System Maintenance & Backup
- W11: Summarization & Reporting
- W12: Code Execution & Analysis
- W13: Translation & Localization
- W14: Sentiment & Tone Analysis
- W15: Hardware I/O & Sensorik

## 3. Observer (Der Wächter)
Ein isolierter Heartbeat-Service, der System-Limits, Memory Leaks und DB-Locks überwacht. Schlägt Alarm bei Latenzen > 200ms.
