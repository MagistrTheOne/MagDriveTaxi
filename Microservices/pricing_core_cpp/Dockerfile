# Multi-stage build для C++ Pricing Service
FROM ubuntu:22.04 as builder

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем исходники и vendor
COPY . .

# Собираем приложение
RUN make build

# Production образ
FROM ubuntu:22.04

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя
RUN useradd --create-home --shell /bin/bash app

# Рабочая директория
WORKDIR /app

# Копируем собранное приложение
COPY --from=builder /app/pricing_service .

# Устанавливаем права
RUN chown app:app pricing_service && chmod +x pricing_service

USER app

# Переменные окружения
ENV PORT=8003
ENV BASE_PRICE=100.0
ENV PRICE_PER_KM=15.0
ENV PRICE_PER_MINUTE=3.0

# Порт
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8003/healthz || exit 1

# Команда запуска
CMD ["./pricing_service"]
