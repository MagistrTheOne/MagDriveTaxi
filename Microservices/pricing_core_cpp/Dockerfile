FROM gcc:11 as builder

# Устанавливаем зависимости для сборки
RUN apt-get update && apt-get install -y \
    nlohmann-json3-dev \
    make \
    && rm -rf /var/lib/apt/lists/*

# Копируем исходный код
WORKDIR /app
COPY . .

# Собираем приложение
RUN make clean && make

# Создаем минимальный образ
FROM debian:bullseye-slim

# Устанавливаем runtime зависимости
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем собранное приложение
COPY --from=builder /app/pricing_service /usr/local/bin/

# Создаем пользователя для безопасности
RUN useradd -r -s /bin/false pricing && \
    chown pricing:pricing /usr/local/bin/pricing_service

USER pricing

# Открываем порт
EXPOSE 7010

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7010/healthz || exit 1

# Запускаем приложение
CMD ["/usr/local/bin/pricing_service"]
