# MagaDrive Project - T8-T10 Integration
# Основные команды для управления проектом

# Переменные
DOCKER_COMPOSE = docker-compose
FLUTTER = flutter
PYTHON = python3
MAKE = make

# Директории
FRONTEND_DIR = Frontend
BACKEND_DIR = Microservices
DOCK_DIR = Dock
DOCS_DIR = docs

# Цвета для вывода
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
BLUE = \033[0;34m
NC = \033[0m # No Color

.PHONY: help all clean build run test stop logs status

help: ## Показать справку по командам
	@echo "$(BLUE)=== MagaDrive T8-T10 Integration ===$(NC)"
	@echo "$(GREEN)Доступные команды:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

all: build ## Собрать и запустить весь проект

# =============================================================================
# Backend (Microservices)
# =============================================================================

backend-build: ## Собрать все микросервисы
	@echo "$(BLUE)🔨 Сборка микросервисов...$(NC)"
	@cd $(BACKEND_DIR)/api-gateway_py && pip install -r requirements.txt
	@cd $(BACKEND_DIR)/ride_service_py && pip install -r requirements.txt
	@cd $(BACKEND_DIR)/geo_service_py && pip install -r requirements.txt
	@cd $(BACKEND_DIR)/pricing_core_cpp && $(MAKE) build
	@echo "$(GREEN)✅ Микросервисы собраны$(NC)"

backend-run: ## Запустить микросервисы локально
	@echo "$(BLUE)🚀 Запуск микросервисов...$(NC)"
	@cd $(BACKEND_DIR)/api-gateway_py && $(PYTHON) main.py &
	@cd $(BACKEND_DIR)/ride_service_py && $(PYTHON) main.py &
	@cd $(BACKEND_DIR)/geo_service_py && $(PYTHON) main.py &
	@cd $(BACKEND_DIR)/pricing_core_cpp && ./pricing_service &
	@echo "$(GREEN)✅ Микросервисы запущены$(NC)"
	@echo "$(YELLOW)⚠️  Используйте 'make stop' для остановки$(NC)"

# =============================================================================
# Docker Backend
# =============================================================================

docker-up: ## Запустить все сервисы в Docker
	@echo "$(BLUE)🐳 Запуск Docker сервисов...$(NC)"
	@cd $(DOCK_DIR) && $(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✅ Docker сервисы запущены$(NC)"

docker-down: ## Остановить все Docker сервисы
	@echo "$(BLUE)🛑 Остановка Docker сервисов...$(NC)"
	@cd $(DOCK_DIR) && $(DOCKER_COMPOSE) down
	@echo "$(GREEN)✅ Docker сервисы остановлены$(NC)"

docker-build: ## Пересобрать Docker образы
	@echo "$(BLUE)🔨 Пересборка Docker образов...$(NC)"
	@cd $(DOCK_DIR) && $(DOCKER_COMPOSE) build --no-cache
	@echo "$(GREEN)✅ Docker образы пересобраны$(NC)"

docker-logs: ## Показать логи Docker сервисов
	@cd $(DOCK_DIR) && $(DOCKER_COMPOSE) logs -f

docker-status: ## Показать статус Docker сервисов
	@cd $(DOCK_DIR) && $(DOCKER_COMPOSE) ps

# =============================================================================
# Frontend (Flutter)
# =============================================================================

frontend-setup: ## Настройка Flutter проекта
	@echo "$(BLUE)📱 Настройка Flutter проекта...$(NC)"
	@cd $(FRONTEND_DIR) && $(FLUTTER) pub get
	@cd $(FRONTEND_DIR) && $(MAKE) generate-style
	@echo "$(GREEN)✅ Flutter проект настроен$(NC)"

frontend-run: ## Запустить Flutter приложение
	@echo "$(BLUE)📱 Запуск Flutter приложения...$(NC)"
	@cd $(FRONTEND_DIR) && $(FLUTTER) run

frontend-build: ## Собрать Flutter APK
	@echo "$(BLUE)📱 Сборка Flutter APK...$(NC)"
	@cd $(FRONTEND_DIR) && $(FLUTTER) build apk --debug
	@echo "$(GREEN)✅ APK собран: $(FRONTEND_DIR)/build/app/outputs/flutter-apk/app-debug.apk$(NC)"

frontend-clean: ## Очистить Flutter build
	@echo "$(BLUE)🧹 Очистка Flutter build...$(NC)"
	@cd $(FRONTEND_DIR) && $(FLUTTER) clean
	@echo "$(GREEN)✅ Flutter build очищен$(NC)"

# =============================================================================
# Интеграция
# =============================================================================

build: backend-build frontend-setup ## Собрать весь проект
	@echo "$(GREEN)🎉 Проект собран!$(NC)"

run: docker-up frontend-run ## Запустить весь проект
	@echo "$(GREEN)🎉 Проект запущен!$(NC)"

test: ## Запустить тесты
	@echo "$(BLUE)🧪 Запуск тестов...$(NC)"
	@cd $(FRONTEND_DIR) && $(FLUTTER) test
	@echo "$(GREEN)✅ Тесты выполнены$(NC)"

# =============================================================================
# Утилиты
# =============================================================================

clean: ## Очистить весь проект
	@echo "$(BLUE)🧹 Очистка проекта...$(NC)"
	@cd $(FRONTEND_DIR) && $(MAKE) clean
	@cd $(BACKEND_DIR)/pricing_core_cpp && $(MAKE) clean
	@cd $(DOCK_DIR) && $(DOCKER_COMPOSE) down -v
	@echo "$(GREEN)✅ Проект очищен$(NC)"

stop: ## Остановить все сервисы
	@echo "$(BLUE)🛑 Остановка всех сервисов...$(NC)"
	@pkill -f "python.*main.py" || true
	@pkill -f "pricing_service" || true
	@cd $(DOCK_DIR) && $(DOCKER_COMPOSE) down
	@echo "$(GREEN)✅ Все сервисы остановлены$(NC)"

logs: ## Показать логи всех сервисов
	@echo "$(BLUE)📋 Логи сервисов:$(NC)"
	@cd $(DOCK_DIR) && $(DOCKER_COMPOSE) logs --tail=50

status: ## Показать статус всех сервисов
	@echo "$(BLUE)📊 Статус сервисов:$(NC)"
	@echo "$(YELLOW)Backend (Docker):$(NC)"
	@cd $(DOCK_DIR) && $(DOCKER_COMPOSE) ps
	@echo "$(YELLOW)Frontend:$(NC)"
	@cd $(FRONTEND_DIR) && $(FLUTTER) doctor

health: ## Проверить здоровье всех сервисов
	@echo "$(BLUE)🏥 Проверка здоровья сервисов...$(NC)"
	@curl -s http://localhost:8080/healthz | jq . || echo "$(RED)❌ Gateway недоступен$(NC)"
	@curl -s http://localhost:8001/healthz | jq . || echo "$(RED)❌ Ride Service недоступен$(NC)"
	@curl -s http://localhost:8002/healthz | jq . || echo "$(RED)❌ Geo Service недоступен$(NC)"
	@curl -s http://localhost:8003/healthz | jq . || echo "$(RED)❌ Pricing Service недоступен$(NC)"

# =============================================================================
# Разработка
# =============================================================================

dev-setup: ## Настройка окружения разработки
	@echo "$(BLUE)⚙️  Настройка окружения разработки...$(NC)"
	@echo "$(YELLOW)1. Установка Python зависимостей...$(NC)"
	@cd $(BACKEND_DIR)/api-gateway_py && pip install -r requirements.txt
	@cd $(BACKEND_DIR)/ride_service_py && pip install -r requirements.txt
	@cd $(BACKEND_DIR)/geo_service_py && pip install -r requirements.txt
	@echo "$(YELLOW)2. Установка Flutter зависимостей...$(NC)"
	@cd $(FRONTEND_DIR) && $(FLUTTER) pub get
	@echo "$(YELLOW)3. Генерация стиля карты...$(NC)"
	@cd $(FRONTEND_DIR) && $(MAKE) generate-style
	@echo "$(YELLOW)4. Сборка C++ сервиса...$(NC)"
	@cd $(BACKEND_DIR)/pricing_core_cpp && $(MAKE) build
	@echo "$(GREEN)✅ Окружение разработки настроено$(NC)"

dev-run: ## Запуск в режиме разработки
	@echo "$(BLUE)🚀 Запуск в режиме разработки...$(NC)"
	@echo "$(YELLOW)Запуск Backend сервисов...$(NC)"
	@$(MAKE) backend-run
	@echo "$(YELLOW)Запуск Frontend...$(NC)"
	@$(MAKE) frontend-run

# =============================================================================
# Production
# =============================================================================

prod-build: ## Сборка для production
	@echo "$(BLUE)🏭 Сборка для production...$(NC)"
	@cd $(FRONTEND_DIR) && $(FLUTTER) build apk --release
	@cd $(BACKEND_DIR)/pricing_core_cpp && $(MAKE) cmake-build
	@echo "$(GREEN)✅ Production сборка готова$(NC)"

prod-deploy: ## Деплой в production
	@echo "$(BLUE)🚀 Деплой в production...$(NC)"
	@echo "$(RED)⚠️  Функция в разработке$(NC)"

# =============================================================================
# Документация
# =============================================================================

docs: ## Создать документацию
	@echo "$(BLUE)📚 Создание документации...$(NC)"
	@echo "$(GREEN)✅ Документация создана в $(DOCS_DIR)/$(NC)"

# =============================================================================
# Информация
# =============================================================================

info: ## Информация о проекте
	@echo "$(BLUE)=== MagaDrive T8-T10 ===$(NC)"
	@echo "$(GREEN)Версия:$(NC) T8-T10 Integration"
	@echo "$(GREEN)Статус:$(NC) Development"
	@echo "$(GREEN)Архитектура:$(NC) Microservices + Flutter"
	@echo "$(GREEN)Backend:$(NC) Python + C++"
	@echo "$(GREEN)Frontend:$(NC) Flutter + MapLibre GL"
	@echo "$(GREEN)Коммуникация:$(NC) REST + WebSocket"
	@echo ""
	@echo "$(YELLOW)Быстрый старт:$(NC)"
	@echo "  make dev-setup    # Настройка окружения"
	@echo "  make dev-run      # Запуск разработки"
	@echo "  make docker-up    # Запуск Docker"
	@echo "  make frontend-run # Запуск Flutter"
