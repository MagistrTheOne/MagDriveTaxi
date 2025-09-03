# MagaDrive Makefile
# Упрощенные команды для разработки

.PHONY: help dev stage prod clean docker-up docker-down docker-logs

help:
	@echo "MagaDrive Development Commands:"
	@echo ""
	@echo "Frontend:"
	@echo "  dev-style     - Generate dev map style"
	@echo "  stage-style   - Generate stage map style (requires MAPTILER_KEY)"
	@echo "  prod-style    - Generate prod map style (requires MAPTILER_KEY)"
	@echo ""
	@echo "Docker:"
	@echo "  docker-up     - Start all services"
	@echo "  docker-down   - Stop all services"
	@echo "  docker-logs   - Show logs for all services"
	@echo ""
	@echo "Clean:"
	@echo "  clean         - Remove generated files"

# Frontend map styles
dev-style:
	@echo "Generating dev map style..."
	@powershell -ExecutionPolicy Bypass -File "scripts/generate_map_style.ps1" -Flavor "dev"

stage-style:
	@echo "Generating stage map style..."
	@if [ -z "$(MAPTILER_KEY)" ]; then \
		echo "Error: MAPTILER_KEY environment variable required"; \
		echo "Usage: make stage-style MAPTILER_KEY=your_key"; \
		exit 1; \
	fi
	@powershell -ExecutionPolicy Bypass -File "scripts/generate_map_style.ps1" -Flavor "stage" -MapTilerKey "$(MAPTILER_KEY)"

prod-style:
	@echo "Generating prod map style..."
	@if [ -z "$(MAPTILER_KEY)" ]; then \
		echo "Error: MAPTILER_KEY environment variable required"; \
		echo "Usage: make prod-style MAPTILER_KEY=your_key"; \
		exit 1; \
	fi
	@powershell -ExecutionPolicy Bypass -File "scripts/generate_map_style.ps1" -Flavor "prod" -MapTilerKey "$(MAPTILER_KEY)"

# Docker commands
docker-up:
	@echo "Starting MagaDrive services..."
	cd Dock && docker compose up -d --build

docker-down:
	@echo "Stopping MagaDrive services..."
	cd Dock && docker compose down

docker-logs:
	@echo "Showing logs for all services..."
	cd Dock && docker compose logs -f

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	@rm -f Frontend/assets/map/style_dark_gold.json
	@echo "Clean complete"

# Default target
all: dev-style docker-up
	@echo "MagaDrive development environment ready!"
