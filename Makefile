PYTHON ?= python3

.PHONY: test prepare build-roundcube

test:
	$(PYTHON) scripts/check_foundation.py

prepare:
	$(PYTHON) scripts/prepare_mcpcube.py

build-roundcube: prepare
	docker build -f docker/roundcube/Dockerfile -t hermesaki-roundcube:dev .
