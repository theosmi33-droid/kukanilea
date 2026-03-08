# PR638 Security Review

## Focus
- Path traversal during update tar extraction.
- Unsafe tar entry types (symlink, hardlink, device).

## Findings
- Extraction now rejects traversal and absolute paths before write.
- Extraction now rejects unsupported tar member types.
- Coverage extended with dedicated security regression tests and a positive contract test.

## Residual Risk
- Archive decompression bombs are still possible if very large archives are accepted upstream.
- Mitigation for archive size limits should be tracked separately in intake/update policy.

