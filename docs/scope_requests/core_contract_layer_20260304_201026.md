# SCOPE REQUEST: core_contract_layer_20260304_201026

## Summary
Antrag auf kontrollierte Änderung im Shared Contract Layer (`app/contracts/tool_contracts.py`) zur Verhinderung von Domain-Drift und zur einheitlichen Durchsetzung des 11-Tool API-Vertrags.

## Files
- app/contracts/tool_contracts.py
- tests/contracts/test_dashboard_chatbot_contract_payloads.py

## Reason
- Overlap-Scanner meldet Allowlist-Verstoß, weil Contract-Logik bewusst zentral liegt.
- Änderung reduziert Cross-Domain-Kopplung, da Read-only Contract-Regeln zentral statt pro Domain dupliziert werden.

## Safety
- Keine neuen Write-Endpunkte.
- Nur Contract-Metadaten (`write_scope`, `cross_domain_writes`, `aggregate_mode`) ergänzt.
- Verhaltensänderung auf API-Schreibrouten: **keine**.
