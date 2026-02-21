# RC_WINDOWS_PREREQUISITES

Date: 2026-02-21

## Windows RC Prerequisites

1. Windows runner/host available (`windows-latest` or self-hosted VM).
2. Windows SDK installed (includes `signtool.exe`).
3. Code-signing certificate installed and accessible for signing step.
4. Signed `.exe` / `.msi` artifact generated.
5. Verification command executed:
   ```powershell
   signtool verify /pa /v <path_to_exe_or_msi>
   ```

## SDK / Tooling Note

- Typical SDK path:
  `C:\Program Files (x86)\Windows Kits\10\bin\<VERSION>\x64\signtool.exe`
- If `signtool` is not in `PATH`, use full path in CI step.

## Exit Code Expectations

- `0`: Verification succeeded.
- `1`: Verification failed.
- `2`: Verification succeeded with warnings.

## Certificate Strategy (OV vs EV)

- `OV` (Organization Validation):
  - Faster acquisition.
  - Lower initial SmartScreen reputation in typical internet-download flows.
- `EV` (Extended Validation):
  - Higher operational/identity requirements.
  - Commonly preferred for better initial trust signals.

Suggested rollout:
- Beta/early RC can start with OV if needed.
- Prod target should move to EV where feasible.

## SmartScreen Caveat

- SmartScreen reputation is not deterministic API output.
- Use consistent publisher identity and track field install feedback over time.

## References

- https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool
- https://signpath.io/knowledge-base/windows-platform
