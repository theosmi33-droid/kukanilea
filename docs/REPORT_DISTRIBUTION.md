# KUKANILEA Desktop Distribution Report

## Build Information
- **OS:** macOS 15.3 (arm64)
- **Date:** 2026-02-23
- **Build Tool:** PyInstaller 6.19.0
- **App Name:** KUKANILEA.app

## Artifacts
| Artifact | Path | Size | SHA256 Hash |
|---|---|---|---|
| macOS App Bundle | `dist/KUKANILEA.app` | 604M | 15beea7da45db726be50b89394f64f8e78e8e7fc375c464d356726e96a7a5ab4 |
| SBOM (CycloneDX) | `dist/evidence/sbom.cdx.json` | - | - |
| SLSA Provenance | `dist/evidence/provenance.json` | - | - |

## Security & Trust
- **Supply Chain:** SBOM and SLSA Provenance generated.
- **Offline Integrity:** All vendor assets (HTMX, Tailwind) bundled locally.
- **Verification:** E2E/Desktop Smoke tests passed prior to bundling.
