FROM ubuntu:22.04

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libmicrohttpd-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование исходного кода
COPY . .

# Сборка приложения
RUN mkdir build && cd build \
    && cmake .. \
    && make -j$(nproc) \
    && chmod +x pricing_core_cpp

# Создание пользователя для безопасности
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=10s --timeout=2s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:7010/healthz || exit 1

EXPOSE 7010

# Запуск приложения
CMD ["./build/pricing_core_cpp"]
