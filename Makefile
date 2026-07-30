PYTHON ?= python

ifeq ($(OS),Windows_NT)
BACKEND_PYTHON := backend/.venv/Scripts/python.exe
NPM ?= cmd.exe //d //c npm
else
BACKEND_PYTHON := backend/.venv/bin/python
NPM ?= npm
endif

.PHONY: setup setup-backend setup-frontend lint lint-backend lint-frontend \
	test test-backend test-frontend build check infra up down

setup: setup-backend setup-frontend

setup-backend:
	$(PYTHON) -m venv backend/.venv
	$(BACKEND_PYTHON) -m pip install -e "backend[dev]"

setup-frontend:
	$(NPM) --prefix frontend ci

lint: lint-backend lint-frontend

lint-backend:
	$(BACKEND_PYTHON) -m ruff check backend
	$(BACKEND_PYTHON) -m ruff format --check backend

lint-frontend:
	$(NPM) --prefix frontend run lint

test: test-backend test-frontend

test-backend:
	$(BACKEND_PYTHON) -m pytest backend

test-frontend:
	$(NPM) --prefix frontend run test

build:
	$(NPM) --prefix frontend run build

check: lint test build
	docker compose config --quiet

infra:
	docker compose up -d postgres redis

up:
	docker compose up --build

down:
	docker compose down
