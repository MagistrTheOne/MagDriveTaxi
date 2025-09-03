CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -O2
LDFLAGS = 

# Зависимости
DEPS = nlohmann/json

# Цели
TARGET = pricing_service
SOURCE = main.cpp

# Правила сборки
$(TARGET): $(SOURCE)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SOURCE) $(LDFLAGS)

# Установка зависимостей (Ubuntu/Debian)
install-deps:
	sudo apt-get update
	sudo apt-get install -y nlohmann-json3-dev

# Установка зависимостей (CentOS/RHEL)
install-deps-centos:
	sudo yum install -y nlohmann-json-devel

# Установка зависимостей (macOS)
install-deps-macos:
	brew install nlohmann-json

# Очистка
clean:
	rm -f $(TARGET)

# Запуск
run: $(TARGET)
	./$(TARGET)

# Тест
test: $(TARGET)
	@echo "Testing pricing service..."
	@echo "POST /price with valid data..."
	@echo '{"distanceM": 5000, "etaSec": 600, "class": "comfort"}' | \
	curl -s -X POST http://localhost:7010/price \
		-H "Content-Type: application/json" \
		-d @- | jq .

# Health check
health:
	@echo "Health check..."
	curl -s http://localhost:7010/healthz | jq .

# Ready check
ready:
	@echo "Ready check..."
	curl -s http://localhost:7010/readyz | jq .

# Docker сборка
docker-build:
	docker build -t magadrive-pricing .

# Docker запуск
docker-run:
	docker run -p 7010:7010 \
		-e PORT=7010 \
		-e DEMAND_MULTIPLIER=1.2 \
		magadrive-pricing

.PHONY: clean run test health ready install-deps install-deps-centos install-deps-macos docker-build docker-run
