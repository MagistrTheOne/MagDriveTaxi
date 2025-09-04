# 🚗 MagaDrive - T8-T10 Integration

**Такси-сервис нового поколения** с интеграцией Frontend (Flutter) и Backend (Microservices) функций.

## 🎯 Что реализовано (T8-T10)

### Frontend (Flutter)
- ✅ **Экраны**: Home, Select, Finding, Assigned, OnTheWay, InRide, Done/Cancel
- ✅ **Карта**: MapLibre GL с MapTiler стилями
- ✅ **WebSocket**: Реальное время обновления поездок
- ✅ **Состояние**: Provider для управления состоянием
- ✅ **UI**: Темная тема с золотыми акцентами

### Backend (Microservices)
- ✅ **API Gateway**: Единая точка входа, прокси и WebSocket relay
- ✅ **Ride Service**: Управление поездками, события и SQLite
- ✅ **Geo Service**: MapTiler прокси и заглушка водителей
- ✅ **Pricing Service**: HTTP расчет стоимости на C++

## 🚀 Быстрый старт

### 1. Клонирование и настройка
```bash
git clone <repository-url>
cd MagaDrive
make dev-setup
```

### 2. Запуск Backend
```bash
make docker-up
```

### 3. Запуск Frontend
```bash
make frontend-run
```

### 4. Проверка статуса
```bash
make health
```

## 🏗️ Архитектура

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Flutter App   │    │   WebSocket     │    │   REST API      │
│   (Frontend)    │◄──►│   Client        │◄──►│   Gateway       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                │                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Ride Service  │    │   Geo Service   │
                       │   (Python)      │    │   (Python)      │
                       └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   SQLite DB     │    │   MapTiler API  │
                       └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Pricing Service │
                       │     (C++)      │
                       └─────────────────┘
```

## 📱 Экраны приложения

| Экран | Описание | Статус |
|-------|----------|---------|
| **Start** | Выбор типа пользователя | ✅ Реализован |
| **Home** | Главная карта и поиск | ✅ Реализован |
| **Select** | Выбор маршрута и класса | ✅ Реализован |
| **Finding** | Поиск водителя | ✅ Реализован |
| **Assigned** | Водитель назначен | ✅ Реализован |
| **OnTheWay** | Водитель в пути | ✅ Реализован |
| **InRide** | В поездке | ✅ Реализован |
| **Done/Cancel** | Завершение/отмена | ✅ Реализован |

## 🔧 Технологии

### Frontend
- **Flutter** 3.x
- **MapLibre GL** для карт
- **Provider** для состояния
- **WebSocket** для real-time

### Backend
- **Python 3.11** + FastAPI
- **C++17** + httplib
- **SQLite** для данных
- **Docker** для контейнеризации

### Интеграции
- **MapTiler** для карт и маршрутов
- **WebSocket** для событий
- **REST API** для CRUD операций

## 📋 API Endpoints

### Gateway (Port 8080)
- `GET /healthz` - Health check
- `GET /readyz` - Ready check
- `POST /v1/rides` - Создание поездки
- `GET /v1/rides/{id}` - Получение поездки
- `POST /v1/rides/{id}/cancel` - Отмена поездки
- `GET /ws/ride/{id}` - WebSocket события

### Ride Service (Port 8001)
- `POST /rides` - Создание поездки
- `GET /rides/{id}` - Получение поездки
- `POST /rides/{id}/cancel` - Отмена поездки

### Geo Service (Port 8002)
- `POST /route/eta` - Расчет маршрута
- `GET /drivers` - Поиск водителей

### Pricing Service (Port 8003)
- `POST /price` - Расчет стоимости

## 🎨 UI/UX Особенности

- **Темная тема** с золотыми акцентами (#D4AF37)
- **Адаптивный дизайн** для всех экранов
- **Анимации** для плавных переходов
- **Карта** с поддержкой жестов
- **Real-time обновления** через WebSocket

## 🚀 Команды разработки

```bash
# Основные команды
make help              # Справка по командам
make dev-setup         # Настройка окружения
make dev-run           # Запуск разработки
make build             # Сборка проекта
make run               # Запуск проекта

# Docker команды
make docker-up         # Запуск Docker сервисов
make docker-down       # Остановка Docker сервисов
make docker-logs       # Просмотр логов
make docker-status     # Статус сервисов

# Frontend команды
make frontend-setup    # Настройка Flutter
make frontend-run      # Запуск Flutter
make frontend-build    # Сборка APK
make frontend-clean    # Очистка build

# Backend команды
make backend-build     # Сборка микросервисов
make backend-run       # Запуск локально

# Утилиты
make clean             # Очистка проекта
make stop              # Остановка всех сервисов
make health            # Проверка здоровья
make status            # Статус всех сервисов
```

## 🧪 Тестирование

### Smoke тесты
```bash
# Health checks
make health

# API тесты
curl -X POST http://localhost:8080/v1/rides \
  -H "Content-Type: application/json" \
  -d '{"origin":"Москва","destination":"СПб","vehicleClass":"comfort"}'
```

### WebSocket тест
```bash
wscat -c ws://localhost:8080/ws/ride/test-123
```

## 📊 Мониторинг

- **Health checks** для всех сервисов
- **Structured logging** с traceId
- **Performance metrics** (response time < 300ms)
- **WebSocket reconnection** < 5s

## 🔒 Безопасность

- **Bearer token** аутентификация
- **CORS** настройки
- **Input validation** на всех уровнях
- **SQL injection** protection

## 📚 Документация

- [T8-T10 Integration Guide](docs/T8-T10_INTEGRATION.md)
- [API Reference](docs/API_REFERENCE.md)
- [Development Guide](docs/DEVELOPMENT.md)

## 🚧 Следующие шаги

1. **T11**: Firebase интеграция
2. **T12**: Платежи
3. **T13**: Push уведомления
4. **T14**: Аналитика
5. **T15**: Production deployment

## 🤝 Участие в разработке

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📄 Лицензия

Этот проект лицензирован под MIT License - см. файл [LICENSE](LICENSE) для деталей.

## 📞 Контакты

- **Команда**: MagaDrive Team
- **Версия**: T8-T10 Integration
- **Статус**: Development
- **Дата**: 2024

---

**MagaDrive** - Такси будущего уже сегодня! 🚗✨
