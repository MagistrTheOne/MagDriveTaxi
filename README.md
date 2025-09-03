# MagDriveTaxi

Luxury Taxi MVP - чистая архитектура, 4 микросервиса, Flutter + MapLibre, без GMS.

## Архитектура

- **Frontend**: Flutter app (dev/stage/prod flavors)
- **Backend**: 4 микросервиса (3×Python, 1×C++)
- **Карты**: MapLibre + MapTiler (без Google Maps)
- **API**: REST v1 + WebSocket события

## Быстрый старт

```bash
# Генерация стиля карты для dev
make dev-style

# Запуск всех сервисов
make docker-up

# Остановка
make docker-down
```

## Структура проекта

```
MagDrive/
├── Frontend/          # Flutter app
├── Backend/           # API контракты и схемы
├── Microservices/     # 4 микросервиса
├── Dock/              # Docker compose
├── scripts/           # Утилиты
└── secrets/           # Локальные секреты
```

## Лицензия

MIT
