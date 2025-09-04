# MagaDrive T8-T10 Integration Guide

## Обзор

Данный документ описывает интеграцию Frontend (T8-T10) и Backend (T8-T10) функций для проекта MagaDrive. Интеграция включает в себя REST API, WebSocket клиент, UI логику и микросервисную архитектуру.

## Архитектура

### Frontend (Flutter)
- **Экраны**: Home, Select, Finding, Assigned, OnTheWay, InRide, Done/Cancel
- **Состояние**: Provider для управления состоянием
- **Карта**: MapLibre GL с MapTiler стилями
- **WebSocket**: Реальное время обновления поездок

### Backend (Microservices)
- **api-gateway_py**: Единая точка входа, прокси и WebSocket relay
- **ride_service_py**: Управление поездками, события и SQLite
- **geo_service_py**: MapTiler прокси и заглушка водителей
- **pricing_core_cpp**: HTTP расчет стоимости

## Быстрый старт

### 1. Запуск Backend

```bash
cd Dock
docker-compose up -d
```

Проверка статуса:
```bash
docker-compose ps
```

### 2. Запуск Frontend

```bash
cd Frontend
flutter run
```

### 3. Генерация стиля карты

```bash
cd Frontend
make generate-style
```

## API Endpoints

### Gateway (Port 8080)
- `GET /healthz` - Health check
- `GET /readyz` - Ready check
- `POST /v1/rides` - Создание поездки
- `GET /v1/rides/{id}` - Получение поездки
- `POST /v1/rides/{id}/cancel` - Отмена поездки
- `POST /v1/route/eta` - Расчет ETA
- `GET /v1/drivers` - Доступные водители
- `GET /ws/ride/{id}` - WebSocket события

### Ride Service (Port 8001)
- `POST /rides` - Создание поездки
- `GET /rides/{id}` - Получение поездки
- `POST /rides/{id}/cancel` - Отмена поездки
- `POST /rides/{id}/complete` - Завершение поездки

### Geo Service (Port 8002)
- `POST /route/eta` - Расчет маршрута
- `GET /drivers` - Поиск водителей

### Pricing Service (Port 8003)
- `POST /price` - Расчет стоимости

## WebSocket Events

```json
{
  "type": "RIDE_CREATED",
  "data": {
    "rideId": "ride_123",
    "status": "requested"
  },
  "eventId": "evt_456",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

Поддерживаемые события:
- `RIDE_CREATED` - Поездка создана
- `DRIVER_ASSIGNED` - Водитель назначен
- `ETA_UPDATE` - Обновление ETA
- `LOCATION_UPDATE` - Обновление позиции
- `RIDE_STATUS_CHANGED` - Изменение статуса
- `RIDE_COMPLETED` - Поездка завершена
- `RIDE_CANCELED` - Поездка отменена

## Конфигурация

### Frontend (.env.dev)
```bash
API_BASE_URL=http://localhost:8080/v1
WS_BASE_URL=ws://localhost:8080/ws
MAPTILER_API_KEY=SjhYKAeXJxWy3pPcQc2G
USE_WS=true
USE_FCM=false
```

### Backend (Docker Compose)
```yaml
environment:
  - MAPTILER_API_KEY=${MAPTILER_API_KEY}
  - BASE_PRICE=100.0
  - PRICE_PER_KM=15.0
  - PRICE_PER_MINUTE=3.0
```

## Разработка

### Сборка C++ сервиса
```bash
cd Microservices/pricing_core_cpp
make build
make run
```

### Сборка Python сервисов
```bash
cd Microservices/api-gateway_py
pip install -r requirements.txt
python main.py
```

### Flutter разработка
```bash
cd Frontend
flutter pub get
flutter run --debug
```

## Тестирование

### Smoke тесты
```bash
# Health checks
curl http://localhost:8080/healthz
curl http://localhost:8001/healthz
curl http://localhost:8002/healthz
curl http://localhost:8003/healthz

# API тесты
curl -X POST http://localhost:8080/v1/rides \
  -H "Content-Type: application/json" \
  -d '{"origin":"Москва","destination":"СПб","vehicleClass":"comfort"}'
```

### WebSocket тест
```bash
# Подключение к WebSocket
wscat -c ws://localhost:8080/ws/ride/test-123
```

## Мониторинг

### Логи
```bash
# Просмотр логов всех сервисов
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f gateway
```

### Метрики
- Response time < 300ms (p95)
- WebSocket reconnection < 5s
- Health check success rate > 99%

## Troubleshooting

### Частые проблемы

1. **Порт занят**
   ```bash
   netstat -tulpn | grep :8080
   ```

2. **MapTiler API недоступен**
   - Проверить API ключ
   - Проверить интернет соединение

3. **WebSocket не подключается**
   - Проверить CORS настройки
   - Проверить firewall

4. **C++ сервис не собирается**
   ```bash
   cd Microservices/pricing_core_cpp
   make clean
   make build
   ```

### Debug режим

```bash
# Frontend
flutter run --debug --verbose

# Backend
docker-compose up --build
```

## Производительность

### Оптимизации
- Кэширование маршрутов (TTL: 600s)
- Connection pooling для HTTP
- WebSocket heartbeat (20s)
- Retry с exponential backoff

### Лимиты
- HTTP timeout: 10s
- WebSocket timeout: 20s
- Max retries: 2
- Connection pool: 10

## Безопасность

### Текущие меры
- Bearer token аутентификация
- CORS настройки
- Input validation
- SQL injection protection

### Рекомендации
- HTTPS в production
- Rate limiting
- API key rotation
- Audit logging

## Следующие шаги

1. **T11**: Firebase интеграция
2. **T12**: Платежи
3. **T13**: Push уведомления
4. **T14**: Аналитика
5. **T15**: Production deployment

## Контакты

- **Разработчик**: MagaDrive Team
- **Версия**: T8-T10
- **Дата**: 2024
- **Статус**: Development
