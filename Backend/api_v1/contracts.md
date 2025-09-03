# MagaDrive API v1 Specification

## Base URL
- **Development**: `http://localhost:8080/v1`
- **Stage**: `https://stage.api.magadrive/v1`
- **Production**: `https://api.magadrive/v1`

## Authentication
- Firebase ID Token в заголовке `Authorization: Bearer <token>`
- Для MVP: аутентификация отключена

## Response Format
```json
{
  "data": {...},
  "error": null,
  "traceId": "uuid-v4"
}
```

## Models

### User
```json
{
  "id": "uuid-v4",
  "phone": "+79001234567",
  "name": "Иван Иванов",
  "role": "user|driver|admin",
  "createdAt": "2025-01-03T20:00:00Z"
}
```

### Driver
```json
{
  "id": "uuid-v4",
  "name": "Петр Петров",
  "rating": 4.8,
  "vehicle": {
    "make": "Toyota",
    "model": "Camry",
    "color": "Черный",
    "plate": "А123БВ77",
    "class": "comfort"
  },
  "photoUrl": "https://..."
}
```

### Ride
```json
{
  "id": "uuid-v4",
  "userId": "uuid-v4",
  "driverId": "uuid-v4",
  "origin": {
    "lat": 55.7558,
    "lng": 37.6176,
    "address": "Красная площадь, 1"
  },
  "dest": {
    "lat": 55.7517,
    "lng": 37.6178,
    "address": "Тверская ул., 1"
  },
  "class": "comfort|business|xl",
  "price": 1500,
  "currency": "RUB",
  "status": "requested|accepted|arriving|ontrip|completed|canceled",
  "etaSec": 900,
  "distanceM": 2500,
  "createdAt": "2025-01-03T20:00:00Z",
  "updatedAt": "2025-01-03T20:05:00Z"
}
```

### DriverLocation
```json
{
  "driverId": "uuid-v4",
  "lat": 55.7558,
  "lng": 37.6176,
  "heading": 90,
  "speed": 15.5,
  "updatedAt": "2025-01-03T20:00:00Z"
}
```

### Error
```json
{
  "code": "RIDE_NOT_FOUND",
  "message": "Поездка не найдена",
  "details": {...}
}
```

## REST Endpoints

### POST /v1/rides
Создание новой поездки

**Headers:**
- `Idempotency-Key: uuid-v4` (обязательно)

**Request:**
```json
{
  "origin": {"lat": 55.7558, "lng": 37.6176},
  "dest": {"lat": 55.7517, "lng": 37.6178},
  "class": "comfort"
}
```

**Response:**
```json
{
  "data": {
    "rideId": "uuid-v4",
    "status": "requested",
    "etaSec": 900,
    "price": 1500
  },
  "error": null,
  "traceId": "uuid-v4"
}
```

### GET /v1/rides/{id}
Получение информации о поездке

**Response:**
```json
{
  "data": { /* Ride object */ },
  "error": null,
  "traceId": "uuid-v4"
}
```

### POST /v1/rides/{id}/cancel
Отмена поездки

**Response:**
```json
{
  "data": {"status": "canceled"},
  "error": null,
  "traceId": "uuid-v4"
}
```

### GET /v1/drivers?bbox=lat1,lng1,lat2,lng2
Поиск водителей в bounding box

**Response:**
```json
{
  "data": [ /* DriverLocation[] */ ],
  "error": null,
  "traceId": "uuid-v4"
}
```

### POST /v1/route/eta
Расчет маршрута и ETA

**Request:**
```json
{
  "origin": {"lat": 55.7558, "lng": 37.6176},
  "dest": {"lat": 55.7517, "lng": 37.6178}
}
```

**Response:**
```json
{
  "data": {
    "etaSec": 900,
    "distanceM": 2500
  },
  "error": null,
  "traceId": "uuid-v4"
}
```

## WebSocket Events

### Connection
- **URL**: `/ws/ride/{rideId}`
- **Protocol**: WebSocket

### Event Format
```json
{
  "type": "event",
  "ts": "2025-01-03T20:00:00Z",
  "payload": {
    "eventType": "RIDE_STATUS_CHANGED",
    "data": {...}
  }
}
```

### Event Types
- `RIDE_CREATED` - поездка создана
- `DRIVER_ASSIGNED` - водитель назначен
- `ETA_UPDATE` - обновление ETA
- `LOCATION_UPDATE` - обновление позиции водителя
- `RIDE_STATUS_CHANGED` - изменение статуса поездки
- `RIDE_COMPLETED` - поездка завершена
- `RIDE_CANCELED` - поездка отменена

## Health Checks
- **Liveness**: `GET /healthz`
- **Readiness**: `GET /readyz`
- **Metrics**: `GET /metrics` (позже)

## Rate Limiting
- Write операции: 10 req/min per user
- Read операции: 100 req/min per user
- WebSocket: без лимитов
