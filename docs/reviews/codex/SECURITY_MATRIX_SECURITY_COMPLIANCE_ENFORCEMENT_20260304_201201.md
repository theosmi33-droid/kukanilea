# Security Matrix Report — SECURITY_COMPLIANCE_ENFORCEMENT_1000

| Control Area | Baseline | Enforcement | Test Coverage | Status |
|---|---|---|---|---|
| Session cookie hardening | Partial defaults | HttpOnly + SameSite + Secure(prod) + `__Host-` in non-dev | `tests/security/test_session_security_defaults.py` | Enforced |
| Confirm gate write actions | Critical-only | Extended to additional admin write endpoints + webhook automation | `tests/security/test_confirm_and_injection_gates.py`, `tests/security/test_security_regressions.py` | Enforced |
| CSP policy | `script-src 'unsafe-inline'` allowed | Consolidated `script-src 'self'`, removed unsafe-inline scripts | `tests/security/test_csp_policy.py`, `tests/security/test_confirm_and_injection_gates.py` | Hardened |
| Chat injection regression | Existing base checks | Added compact-chat injection regression scenario | `tests/security/test_security_regressions.py` | Enforced |
| Route abuse / prefix bypass | Possible read-only prefix bypass via `/admin/settings` | Reduced read-only allowlist to license upload path only | `tests/security/test_security_regressions.py`, `tests/license/test_read_only_enforcement.py` | Enforced |
| License read-only bypass | Broad write allowlist | Explicitly block admin settings writes when read-only (except license upload endpoint) | `tests/license/test_read_only_enforcement.py` | Enforced |
