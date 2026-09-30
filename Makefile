# Xeno / Ziran Philosophical Runtime — developer entry points. Requires python3.11+ and node 20+.
PY ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: setup dev backend frontend build test lint bench fixtures docker docker-run clean experiments experiments-reduction experiments-reason

setup:            ## create venv, install backend (editable, dev extras) and frontend deps
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -e "backend[dev]"
	cd frontend && npm ci

build:            ## build the frontend into frontend/dist (served by the backend)
	cd frontend && npm run build

dev: build        ## run the single service on :3011 (API + UI)
	$(BIN)/uvicorn xzr.service.app:app --app-dir backend --host 127.0.0.1 --port 3011

backend:          ## backend only, for use with `make frontend` (Vite on :5173 proxies to :3011)
	$(BIN)/uvicorn xzr.service.app:app --app-dir backend --host 127.0.0.1 --port 3011 --reload

frontend:
	cd frontend && npm run dev

test:             ## all automated tests
	cd backend && ../$(BIN)/python -m pytest -q
	cd frontend && npm test

lint:             ## ruff + mypy + eslint + tsc
	cd backend && ../$(BIN)/ruff check xzr tests bench scripts && ../$(BIN)/python -m mypy xzr
	cd frontend && npm run lint && npm run typecheck

fixtures:         ## regenerate cross-language protocol fixtures after changing the wire format
	$(BIN)/python backend/scripts/make_fixtures.py

bench:            ## performance benchmark (10k configurations, >50k connections)
	$(BIN)/python backend/bench/benchmark.py

experiments-reduction:  ## primitive reduction study (stage 1 + audits + stage 2), ~25 min on 8 cores
	cd backend && ../$(BIN)/python experiments/run_reduction.py

experiments-reason:     ## reasoning-layer non-redundancy suite, writes backend/experiments/results/reason.json
	cd backend && OMP_NUM_THREADS=1 ../$(BIN)/python -m xzr.experiments.reason experiments/results/reason.json

experiments: experiments-reduction experiments-reason

docker:
	docker build -t xeno-ziran-runtime .

docker-run:
	docker run --rm -p 8080:8080 xeno-ziran-runtime

clean:
	rm -rf frontend/dist backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache
