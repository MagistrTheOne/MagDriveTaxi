# MagaDrive Pricing Service C++ - T8-T10
# Makefile для сборки и управления

CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -O2 -Ivendor
LDFLAGS = -pthread

# Переменные окружения
PORT ?= 8003
BASE_PRICE ?= 100.0
PRICE_PER_KM ?= 15.0
PRICE_PER_MINUTE ?= 3.0

# Файлы
TARGET = pricing_service
SOURCES = main.cpp
VENDOR_DIR = vendor

# Основные команды
.PHONY: all build clean run test install help

all: build ## Собрать все

build: $(TARGET) ## Собрать сервис
	@echo "✅ Pricing Service собран: $(TARGET)"

$(TARGET): $(SOURCES)
	@echo "🔨 Компиляция Pricing Service..."
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SOURCES) $(LDFLAGS)

clean: ## Очистить артефакты сборки
	@echo "🧹 Очистка..."
	rm -f $(TARGET)
	rm -rf build/

run: build ## Запустить сервис
	@echo "🚀 Запуск Pricing Service на порту $(PORT)..."
	PORT=$(PORT) \
	BASE_PRICE=$(BASE_PRICE) \
	PRICE_PER_KM=$(PRICE_PER_KM) \
	PRICE_PER_MINUTE=$(PRICE_PER_MINUTE) \
	./$(TARGET)

test: build ## Тестирование сервиса
	@echo "🧪 Тестирование Pricing Service..."
	@echo "⚠️  Для полного тестирования запустите 'make run' и проверьте эндпоинты"
	@echo "   GET  http://localhost:$(PORT)/healthz"
	@echo "   GET  http://localhost:$(PORT)/readyz"
	@echo "   POST http://localhost:$(PORT)/price"

# Docker команды
docker-build: ## Собрать Docker образ
	@echo "🐳 Сборка Docker образа..."
	docker build -t magadrive/pricing-service .

docker-run: docker-build ## Запустить в Docker
	@echo "🐳 Запуск в Docker на порту $(PORT)..."
	docker run --rm -p $(PORT):$(PORT) \
		-e PORT=$(PORT) \
		-e BASE_PRICE=$(BASE_PRICE) \
		-e PRICE_PER_KM=$(PRICE_PER_KM) \
		-e PRICE_PER_MINUTE=$(PRICE_PER_MINUTE) \
		magadrive/pricing-service

# Установка зависимостей (для разработки)
install-deps: ## Установить зависимости разработки
	@echo "📦 Установка зависимостей для разработки..."
	@if [ ! -d "$(VENDOR_DIR)" ]; then mkdir -p $(VENDOR_DIR); fi
	@if [ ! -d "$(VENDOR_DIR)/nlohmann" ]; then mkdir -p $(VENDOR_DIR)/nlohmann; fi
	@echo "ℹ️  Vendor заглушки уже созданы в $(VENDOR_DIR)/"
	@echo "💡 Для production замените заглушки на полные библиотеки:"
	@echo "   - httplib.h: https://github.com/yhirose/cpp-httplib"
	@echo "   - nlohmann/json.hpp: https://github.com/nlohmann/json"

# CMake сборка (альтернатива)
cmake-build: ## Сборка через CMake
	@echo "🔨 CMake сборка..."
	mkdir -p build
	cd build && cmake .. -DCMAKE_BUILD_TYPE=Release
	cd build && make

cmake-debug: ## Debug сборка через CMake
	@echo "🔨 CMake Debug сборка..."
	mkdir -p build
	cd build && cmake .. -DCMAKE_BUILD_TYPE=Debug
	cd build && make

# Проверка кода
check: ## Проверка кода
	@echo "🔍 Проверка кода..."
	@if command -v cppcheck >/dev/null 2>&1; then \
		cppcheck --enable=all --std=c++17 $(SOURCES); \
	else \
		echo "⚠️  cppcheck не найден, пропускаем статический анализ"; \
	fi

# Форматирование кода
format: ## Форматирование кода
	@echo "✨ Форматирование кода..."
	@if command -v clang-format >/dev/null 2>&1; then \
		clang-format -i $(SOURCES); \
		echo "✅ Код отформатирован"; \
	else \
		echo "⚠️  clang-format не найден, пропускаем форматирование"; \
	fi

# Информация
info: ## Информация о проекте
	@echo "=== MagaDrive Pricing Service C++ ==="
	@echo "Версия: 1.0.0 T8-T10"
	@echo "Порт: $(PORT)"
	@echo "Компилятор: $(CXX)"
	@echo "Флаги: $(CXXFLAGS)"
	@echo "Исходники: $(SOURCES)"
	@echo "Vendor: $(VENDOR_DIR)/"
	@echo ""
	@echo "Эндпоинты:"
	@echo "  GET  /healthz - Health check"
	@echo "  GET  /readyz  - Ready check"
	@echo "  POST /price   - Расчет стоимости"

help: ## Показать помощь
	@echo "MagaDrive Pricing Service C++ - Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
