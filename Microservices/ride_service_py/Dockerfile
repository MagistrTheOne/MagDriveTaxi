FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Создание пользователя для безопасности
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=10s --timeout=2s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:7031/healthz || exit 1

EXPOSE 7031

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7031"]
