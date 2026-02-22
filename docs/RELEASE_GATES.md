# KUKANILEA Release Gates

Dieses Dokument definiert die verbindlichen Bedingungen für Software-Releases (Beta, RC, Prod).

## 1. Quality Gates (Deterministic)

| Gate-ID | Beschreibung | Beta-Anforderung | RC/Prod-Anforderung |
|---------|--------------|------------------|---------------------|
| **Q-SCAN** | Security Scan (Bandit/Safety) | 0 High / 0 P0 | 0 High / 0 P0 |
| **Q-LINT** | Code Style & Linting (Ruff) | All Clear | All Clear |
| **Q-TEST** | Unit & Integration Tests | > 80% Coverage | 100% Critical Paths |
| **Q-E2E** | Top-20 E2E Flows (Playwright) | Smoke (5) PASS | Top-20 PASS |
| **Q-PERF** | Endurance Run (60 min) | Warn-only | PASS (no regression) |

## 2. Platform Gates (Distribution)

| Gate-ID | Beschreibung | Beta | RC/Prod |
|---------|--------------|------|---------|
| **D-MAC** | macOS Notarization & Stapling | BLOCKED allowed | **REQUIRED** |
| **D-WIN** | Windows SignTool Verification | BLOCKED allowed | **REQUIRED** |

## 3. Compliance Gates

| Gate-ID | Beschreibung | Nachweis |
|---------|--------------|----------|
| **C-GDPR** | No PII in logs, Data Minimization | Security Audit Log |
| **C-A11Y** | WCAG 2.2 / EN 301 549 Baseline | `REPORT_HARDENING_UX.md` |
| **C-SBOM** | CycloneDX SBOM generated | `sbom.cdx.json` |

---
*Status: Dieses Dokument ist die einzige Quelle für Go/No-Go Entscheidungen.*
