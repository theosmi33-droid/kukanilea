.PHONY: bootstrap doctor test-smoke test-full

bootstrap:
	./scripts/bootstrap.sh

doctor:
	./scripts/doctor.sh

test-smoke:
	./scripts/doctor.sh --json >/tmp/doctor-report.json
	pytest -q tests/devtools tests/test_error_ux.py

test-full:
	pytest -q
