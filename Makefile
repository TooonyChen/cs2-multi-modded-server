.PHONY: test config build smoke up down

test:
	python3 -m unittest discover -s runtime -v
	python3 -m unittest discover -s tools/legacy-maintenance -v

config:
	docker compose config --quiet

build:
	docker build --platform=linux/amd64 -t cs2-multi-local:latest .

smoke:
	python3 runtime/docker_smoke.py

up:
	docker compose up -d

down:
	docker compose down
