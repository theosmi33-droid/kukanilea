.PHONY: bootstrap doctor test-smoke

bootstrap:
	./scripts/bootstrap.sh

doctor:
	./scripts/doctor.sh

test-smoke:
	pytest -q tests --ignore=tests/e2e
