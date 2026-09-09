PYTHON ?= python3
VENV := .venv/bin/python
.PHONY: test unit integration dev seed prepare build-roundcube stop credentials backup restore-test deploy
.venv/bin/python:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -r requirements.txt
prepare:
	$(PYTHON) scripts/prepare_mcpcube.py
build-roundcube: prepare
	docker build -f docker/roundcube/Dockerfile -t hermesaki-roundcube:dev .
dev: client-build .venv/bin/python build-roundcube
	$(VENV) scripts/dev.py
seed:
	docker compose run --rm api python -m hermesaki.seed
unit: .venv/bin/python
	$(PYTHON) scripts/check_foundation.py
	PYTHONPATH=src $(VENV) -m unittest discover -s tests -v
integration: client-build
	docker compose build api
	docker compose up -d api worker receiver
	docker compose restart edge
	docker compose run --rm api python /app/tests/integration.py
test: unit integration client-test client-live
stop:
	docker compose stop
credentials:
	docker compose run --rm api python -c 'from hermesaki.config import Config; from hermesaki.store import Store; import json; s=Store(Config.load().state); a=json.load(open("/state/accounts.json")); [(print(x["email"],s.open(s.inbox(x["id"])["secret"],x["id"]))) for x in a]'
backup: .venv/bin/python
	@test -n "$(FILE)" -a -n "$(KEY)" || (echo 'Use make backup FILE=/safe/snapshot KEY=/separate/key'; exit 1)
	$(VENV) scripts/backup.py backup "$(FILE)" --key-file "$(KEY)"
restore-test: .venv/bin/python
	$(VENV) scripts/restore_rehearsal.py
deploy: client-build .venv/bin/python prepare
	$(VENV) scripts/preflight.py
	docker compose -f compose.production.yaml build
	docker compose -f compose.production.yaml up -d

.PHONY: landing
landing:
	$(PYTHON) -m http.server 19190 --bind 127.0.0.1 --directory landing

.PHONY: client-build client-test client-live browser-test
client-build:
	npm ci --ignore-scripts
	npm run build
client-test:
	npm test
client-live:
	npm run test:live
browser-test:
	npm run test:browser

.PHONY: clean-test
clean-test: client-build .venv/bin/python build-roundcube
	$(VENV) scripts/clean_acceptance.py
