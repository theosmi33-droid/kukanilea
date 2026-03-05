#!/usr/bin/env bash
set -u

# Exit codes:
# 0 = pass
# 10 = dependency audit failed
# 20 = baseline security tests failed
# 30 = security pytest suite failed

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR" || exit 30

if python -m pip_audit --help >/dev/null 2>&1; then
  python -m pip_audit >/tmp/security_gate_pip_audit.log 2>&1
  audit_rc=$?
  if [[ $audit_rc -ne 0 ]]; then
    if rg -q "ProxyError|MaxRetryError|Connection|Tunnel connection failed" /tmp/security_gate_pip_audit.log; then
      python -m pip check >/tmp/security_gate_pip_check.log 2>&1 || {
        cat /tmp/security_gate_pip_check.log
        exit 10
      }
    else
      cat /tmp/security_gate_pip_audit.log
      exit 10
    fi
  fi
else
  python -m pip check >/tmp/security_gate_pip_check.log 2>&1 || {
    cat /tmp/security_gate_pip_check.log
    exit 10
  }
fi

pytest -q tests/security/test_baseline_controls.py >/tmp/security_gate_baseline.log 2>&1 || {
  cat /tmp/security_gate_baseline.log
  exit 20
}

pytest -q tests/security >/tmp/security_gate_security.log 2>&1 || {
  cat /tmp/security_gate_security.log
  exit 30
}

exit 0
