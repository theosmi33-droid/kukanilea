Status: Lokal konsistent, Remote-Abgleich aktuell nicht möglich.

Befunde: Die Settings-Texte, lokalen Runtime-Hinweise und Produktstatus-Bezeichnungen wurden auf einen konsistenten Stand gebracht (einheitlich deutsch, lokale Runtime klar benannt). Ein Drift-Abgleich gegen `origin/main` ist in dieser Umgebung nicht möglich, da kein `origin`-Remote konfiguriert ist.

Nächster Schritt: Sobald `origin` wieder verfügbar ist, `git fetch origin --prune` und einen kurzen Diff-/Smoke-Check gegen `origin/main` ausführen.

NEEDS_CODEX: no
