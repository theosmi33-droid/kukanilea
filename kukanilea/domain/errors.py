from __future__ import annotations


class DomainError(RuntimeError):
    pass


class TenantViolation(DomainError):
    pass


class PolicyDenied(DomainError):
    pass
