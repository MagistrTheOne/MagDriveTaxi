# MagaDrive Docker Environment

## Обзор
Docker Compose оркестрация для 4 микросервисов MagaDrive MVP.

## Сервисы

### 1. api-gateway_py (8080)
- **Публичный порт**: 8080
- **Внутренний**: http://gateway:8080
- **Зависимости**: ride, geo, pricing
- **Секреты**: firebase_admin.json (RO)

### 2. ride_service_py (7031)
- **Внутренний**: http://ride:7031
- **База данных**: SQLite volume `/data`
- **Секреты**: firebase_admin.json (RO)

### 3. geo_service_py (7032)
- **Внутренний**: http://geo:7032
- **MapTiler**: API ключ из ENV
- **Кэш**: TTL 600 секунд

### 4. pricing_core_cpp (7010)
- **Внутренний**: http://pricing:7010
- **Профили**: comfort, business, xl

## Сеть
- **magadrive_net**: bridge сеть для внутреннего взаимодействия
- **Публичен только gateway:8080**

## Переменные окружения

### Глобальные
```bash
ENV=dev|stage|prod
TRACE_SAMPLER=ratio:0.1
TZ=UTC
```

### Gateway
```bash
PORT=8080
RIDES_URL=http://ride:7031
GEO_URL=http://geo:7032
PRICING_URL=http://pricing:7010
GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/firebase_admin.json
FIREBASE_PROJECT_ID=magadrive-34f8d
```

### Ride Service
```bash
PORT=7031
DB_URL=sqlite:////data/ride.db
EVENT_BUS=ws
GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/firebase_admin.json
FIREBASE_PROJECT_ID=magadrive-34f8d
```

### Geo Service
```bash
PORT=7032
MAP_GEO_PROVIDER=maptiler
MAPTILER_API_KEY=<секрет>
CACHE_TTL_SEC=600
```

### Pricing Service
```bash
PORT=7010
PRICING_PROFILE=comfort|business|xl
```

## Секреты
- **firebase_admin.json**: Firebase Admin SDK ключ
- **MAPTILER_API_KEY**: API ключ MapTiler (только в ENV)

## Запуск

### Development
```bash
cd Dock
$env:MAPTILER_API_KEY="SjhYKAeXJxWy3pPcQc2G"  # PowerShell
docker compose up -d --build
```

### Production
```bash
cd Dock
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Health Checks
- **Gateway**: http://localhost:8080/healthz
- **Ride**: http://localhost:7031/healthz (внутренний)
- **Geo**: http://localhost:7032/healthz (внутренний)
- **Pricing**: http://localhost:7010/healthz (внутренний)

## Логи
- **Формат**: JSON stdout
- **Поля**: ts, level, service, path, status, durMs, traceId
- **Безопасность**: токены/ключи не логируются

## Мониторинг
- **Liveness**: /healthz
- **Readiness**: /readyz
- **Metrics**: /metrics (позже)

## Troubleshooting

### Сервис не поднимается
1. Проверить health check: `curl http://localhost:PORT/healthz`
2. Проверить логи: `docker compose logs SERVICE_NAME`
3. Проверить зависимости: `docker compose ps`

### Секреты не монтируются
1. Проверить путь: `../secrets/firebase_admin.json`
2. Проверить права доступа к файлу
3. Перезапустить: `docker compose down && docker compose up -d`
