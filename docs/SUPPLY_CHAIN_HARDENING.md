# SUPPLY_CHAIN_HARDENING

Date: 2026-02-21

## Scope
Operational supply-chain controls for RC/Prod evidence.

## Required Controls

1. SBOM generation per release artifact.
2. Vulnerability scan summary attached to release.
3. Build hash manifest for reproducibility checks.
4. Build provenance statement (SLSA-style schema).
5. Optional signed attestations roadmap (Sigstore/cosign).

## SBOM Formats

- Primary: CycloneDX JSON.
- Optional enterprise/procurement path: SPDX JSON.
- Tooling:
  - `scripts/generate_sbom.py --format cyclonedx`
  - `scripts/generate_sbom.py --format spdx`

## VEX / VDR / BoV Process

- For each unresolved vulnerability finding:
  - classify exploitability/impact,
  - mark status (`affected`, `not_affected`, `fixed`, `mitigated`),
  - link supporting evidence.

## Provenance

- Generate provenance statement using:
  - `scripts/generate_provenance.py`
- Include builder identity, invocation id, artifact digests.

## Build Manifest

- Generate deterministic hash manifest:
  - `scripts/generate_build_manifest.py`

## Reference Links

- CycloneDX capabilities: https://cyclonedx.org/capabilities
- SPDX standard reference: https://www.iso.org/standard/93810.html
- SLSA provenance: https://slsa.dev/spec/v1.0-rc1/provenance
- Sigstore verify docs: https://docs.sigstore.dev/cosign/verifying/verify/
