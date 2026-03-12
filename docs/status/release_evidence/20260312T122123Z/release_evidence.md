# Release Evidence Bundle

- Timestamp (UTC): `20260312T122123Z`
- Branch: `work`
- Commit: `527b7b7df4b63b511f019d17ec9d270c72e29762`
- Overall status: **PASS**

## Check Matrix

| Check | Status | Exit | Command | Log |
|---|---|---:|---|---|
| guardrails | PASS | 0 | `python3 scripts/ops/verify_guardrails.py` | `docs/status/release_evidence/20260312T122123Z/logs/guardrails.log` |
| healthcheck | PASS | 0 | `bash scripts/ops/healthcheck.sh --skip-pytest` | `docs/status/release_evidence/20260312T122123Z/logs/healthcheck.log` |
| relevant_tests | PASS | 0 | `python3 -m pytest -q tests/security/test_verify_guardrails.py tests/test_release_validator.py` | `docs/status/release_evidence/20260312T122123Z/logs/relevant_tests.log` |
| security_gate | PASS | 0 | `bash scripts/ops/security_gate.sh` | `docs/status/release_evidence/20260312T122123Z/logs/security_gate.log` |

## Packaging Evidence

| File | SHA256 | Size (bytes) |
|---|---|---:|
| `pyproject.toml` | `c9c05eba8426e4818a5bb16e1d941b68c1e4d05d8d1feb8d3f899cb2d8ed72be` | 839 |
| `requirements.txt` | `a59c78d99bf5211f01f584500d1849d4609d840192b1c3e67231c7aa54cb0ebc` | 601 |
| `requirements.lock` | `90b5b6bb5dff483744297c08c33ed5c5f47728c97fa9dd1496c19e1ae0fd8108` | 1835 |
| `package.json` | `f5fded1bbbde918e62d24c1647932427d867b666e1a57c03886456913048fa50` | 187 |
| `package-lock.json` | `be587523c3063305054c45eb43ae3248cb4a7918ba333e55d03db3ae37d2cd0c` | 2235 |

## Git Status Snapshot

```
## work
 M docs/LAUNCH_EVIDENCE_CHECKLIST.md
 M instance/hardware_profile.json
?? MEMORY__KUKANILEA.md
?? MEMORY__KUKANILEA.md.lock
?? scripts/ops/release_evidence_bundle.py
```
