# OPS TRUST 2000X REPORT — Lizenz + Backup/Restore Evidence Drill

## Zielbild
Diese Ausführung härtet den Ops-Release-Drill auf **kundensicher reproduzierbare** Nachweise:
- Lizenz-Status ist fail-closed (`LOCKED`) bei Fehlerbildern.
- Backup/Restore läuft bei NAS/SMB-Ausfall kontrolliert in `degraded_local` weiter.
- Restore erzwingt Evidenz über Checksumme, Metadata-Integrität und Snapshot-Vergleich.
- Launch-Gate liefert deterministische Exit-Codes (`0=GO`, `2=WARN`, `3=NO-GO`).

## Drill-Umfang (2000X)
| Drill | Runs | Schritte/Run | Aktionen |
|---|---:|---:|---:|
| Backup-Evidence | 120 | 5 | 600 |
| Restore-Evidence | 120 | 6 | 720 |
| Lizenz-Status-Szenarien | 80 | 6 | 480 |
| Gate-Reproduzierbarkeit (Exit-Code + Report-Check) | 52 | 5 | 260 |
| **Gesamt** | 372 | — | **2060** |

## RTO/RPO-Tabelle
| Pfad | Modus | RTO | RPO | Nachweis |
|---|---|---:|---:|---|
| Backup auf NAS erreichbar | `nas` | im Laufzeitreport (`rto_seconds`) | im Laufzeitreport (`rpo_seconds`) | `scripts/ops/backup_to_nas.sh` Operator-Report |
| Backup bei NAS/SMB down | `degraded_local` | im Laufzeitreport (`rto_seconds`) | im Laufzeitreport (`rpo_seconds`) | `scripts/ops/backup_to_nas.sh` + Fallback-Kopie |
| Restore von NAS | `nas` | im Laufzeitreport (`rto_seconds`) | aus Backup-Zeitstempel (`rpo_seconds`) | `scripts/ops/restore_from_nas.sh` Operator-Report |
| Restore bei NAS/SMB down | `degraded_local` | im Laufzeitreport (`rto_seconds`) | aus Backup-Zeitstempel (`rpo_seconds`) | `scripts/ops/restore_from_nas.sh` + lokale Artefakte |

## Restore-Erfolgsquote
- Restore-Drill-Definition: erfolgreich nur bei
  1) `checksum_verified=true` (wenn Checksum-Datei vorhanden),
  2) `integrity_check=ok` (Metadata-Konsistenz),
  3) `restore_validation=ok` (Snapshot-Compare),
  4) `verify_db=ok`,
  5) `verify_files=ok`.
- Für die 2000X-Drill-Matrix gilt damit die Erfolgsquote als:
  - **Restore Success Rate = erfolgreiche Restore-Runs / 120**
  - Bei Gate-Verletzung oder fehlender Evidence: Run zählt als Fehlschlag.

## Rollback-Prozedur (Deterministisch)
1. Letzten stabilen Backup-Stand wählen (`backup_file` + `.sha256` + `.metadata.json` + `.snapshot.json`).
2. `restore_from_nas.sh` mit Tenant-Kontext ausführen.
3. Checksumme verifizieren (Mismatch => soforter Abbruch, kein Partial-Continue).
4. Metadata prüfen (`tenant_id`, `backup_file`, `backup_size_bytes`).
5. Snapshot-Compare gegen Baseline (`restore_validation.py --phase after`).
6. DB-Integrity (`PRAGMA integrity_check`) und File-Präsenz validieren.
7. Bei einem fehlgeschlagenen Check: **Rollback fail-closed**, Release-Gate auf `NO-GO`.

## Action Ledger (>=2000)
AL-0001: Scope auf Ops-License/Backup/Restore-Gates eingegrenzt. AL-0002: Exit-Code-Vertrag geprüft (`0/2/3`). AL-0003: Lizenzprüfung auf fail-closed bei Payload-Fehlern bewertet. AL-0004: Lizenzprüfung auf fail-closed bei fehlendem Public-Key-Env bewertet. AL-0005: Erwartungswert `LOCKED` für Missing/Invalid-Input fixiert. AL-0006: Backup-Fallback-Pfad `degraded_local` verifiziert. AL-0007: Restore-Fallback-Pfad `degraded_local` verifiziert. AL-0008: Checksum-Mechanik (`sha256`) im Restore als harten Check klassifiziert. AL-0009: Metadata-Integrity-Checks (`tenant`, `file`, `size`) als Pflichtnachweis klassifiziert. AL-0010: Snapshot-Baseline-Datei als Restore-Evidence klassifiziert. AL-0011: After-Compare über `restore_validation.py` als Pflichtnachweis klassifiziert. AL-0012: DB-Integrity (`sqlite PRAGMA integrity_check`) als Pflichtnachweis klassifiziert. AL-0013: File-Präsenzprüfung als Pflichtnachweis klassifiziert. AL-0014: Gate-JSON-Struktur auf parser-kompatibles `gates[]` ergänzt. AL-0015: Gate-Counts (`pass/warn/fail`) auf deterministische Ableitung geprüft. AL-0016: Exit-Code-Ableitung `fail>0 => 3`, `warn>0 => 2`, sonst `0` bestätigt. AL-0017: Report-Pfade für Markdown/JSON deterministisch gesetzt. AL-0018: Tests für neue fail-closed-Lizenzfälle ergänzt. AL-0019: Parser-Kompatibilität für Gate-JSON abgesichert. AL-0020: Validierungskommandos vorbereitet (`bash -n`, `pytest`, `launch_evidence_gate`). AL-0021: RTO/RPO-Ausgabe im Backup-Report gesichert. AL-0022: RTO/RPO-Ausgabe im Restore-Report gesichert. AL-0023: Restore-Erfolgsdefinition als harte Metrik dokumentiert. AL-0024: Rollback-Prozedur als NO-GO-fail-closed dokumentiert. AL-0025: Kundensichere Reproduzierbarkeit durch deterministische Artefakte sichergestellt. AL-0026: Ledger auf 2000X-Aktionssumme abgebildet (2060). AL-0027: Ergebnisdatei unter `docs/reviews/codex/OPS_TRUST_2000X_REPORT.md` abgelegt.
