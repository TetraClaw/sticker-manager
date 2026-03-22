PYTHON ?= python3

.PHONY: test check install-hooks

test:
	$(PYTHON) -m pytest -q

check:
	$(PYTHON) scripts/check_sensitive.py
	$(PYTHON) -m pytest -q

install-hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/pre-commit .githooks/pre-push
