.PHONY: install run dashboard trends notify docker docker-up docker-down check-feeds clean

install:      ## Set up venv + deps + .env
	./install.sh

run:          ## One command: collect + serve dashboard
	python run.py

dashboard:    ## Dashboard only, no collection
	python run.py dashboard

trends:       ## Run just the social trend collectors
	python run.py trends

notify:       ## Send a digest + weekly report now
	python run.py notify

check-feeds:  ## Validate every RSS feed URL in config/sources.yaml
	./scripts/check-feeds.sh

docker:       ## Build the container image
	docker build -t geowatch .

docker-up:    ## Run via docker compose (SQLite)
	docker compose up

docker-mongo: ## Run via docker compose with MongoDB
	docker compose --profile mongo up

docker-down:  ## Stop docker compose services
	docker compose down

clean:        ## Remove venv, caches, __pycache__
	rm -rf .venv **/__pycache__ scripts/feed-health-report.csv
