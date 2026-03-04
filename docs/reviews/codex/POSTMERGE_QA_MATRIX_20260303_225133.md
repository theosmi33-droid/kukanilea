# POSTMERGE QA MATRIX
Timestamp: 20260303_225133

## Domain Matrix

| Domain | Status | Git Status | Ahead/Behind | Overlap | Test Status |
|---|---|---|---|---|---|
| **dashboard** | 🟡 | UNCLEAN | 0 / 0 | OK(no_diff) | PASS (Global) |
| **upload** | 🟡 | UNCLEAN | 0 / 0 | OK(no_diff) | PASS (Global) |
| **emailpostfach** | 🟢 | CLEAN | 0 / 0 | OK(no_diff) | PASS (Global) |
| **messenger** | 🔴 | UNCLEAN | ERROR | FAIL (Overlap) | PASS (Global) |
| **kalender** | 🔴 | CLEAN | 0 / 18 | FAIL (Overlap) | PASS (Global) |
| **aufgaben** | 🟢 | CLEAN | 0 / 4 | OK(no_diff) | PASS (Global) |
| **zeiterfassung** | 🔴 | CLEAN | 0 / 6 | FAIL (Overlap) | PASS (Global) |
| **projekte** | 🟢 | CLEAN | 0 / 11 | OK(no_diff) | PASS (Global) |
| **visualizer** | 🟡 | UNCLEAN | 0 / 0 | OK | PASS (Global) |
| **einstellungen** | 🟡 | UNCLEAN | ERROR | OK(no_diff) | PASS (Global) |
| **chatbot** | 🟢 | CLEAN | 0 / 0 | OK | PASS (Global) |

## Overall Assessment
**Gesamtfazit: NO-GO** (Wegen kritischer Overlaps in Messenger, Kalender und Zeiterfassung).

### Blocker Details
- **Messenger:** Domain Overlap detektiert + Git Branch Sync Fehler.
- **Kalender:** Domain Overlap detektiert + 18 Commits hinter Origin.
- **Zeiterfassung:** Domain Overlap detektiert.
- **E2E Tests:** Globaler Test `test_full_workflow` schlug fehl (FileNotFoundError bei Cleanup), was auf Instabilität in der Testumgebung hindeutet.

### Legende
- 🟢 **PASS:** Sauber, Synchron, Kein Overlap.
- 🟡 **WARN:** Unsauberer Status oder geringer Rückstand, aber funktional.
- 🔴 **FAIL:** Overlap-Konflikt oder kritischer Rückstand/Fehler.
