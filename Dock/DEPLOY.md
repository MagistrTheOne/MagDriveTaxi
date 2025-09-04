# MagaDrive Production Deployment

## 🚀 Railway Deployment

### 1. Подготовка
```bash
# Клонировать репозиторий
git clone https://github.com/your-username/magadrive.git
cd magadrive/Dock

# Установить Railway CLI
npm install -g @railway/cli

# Войти в Railway
railway login
```

### 2. Создание проекта
```bash
# Создать новый проект
railway init

# Добавить переменные окружения
railway variables set MAPTILER_API_KEY=SjhYKAeXJxWy3pPcQc2G
railway variables set ENVIRONMENT=production
railway variables set NODE_ENV=production
```

### 3. Деплой
```bash
# Деплой на Railway
railway up

# Проверить статус
railway status

# Посмотреть логи
railway logs
```

### 4. Проверка
```bash
# Health check
curl https://your-app.railway.app/healthz

# Ready check
curl https://your-app.railway.app/readyz
```

## 📱 Frontend APK

### Готовый APK
- **Файл**: `Frontend/build/app/outputs/flutter-apk/MagDrive.apk`
- **Размер**: 75.3 МБ
- **Версия**: 1.0.0+1
- **Готов для**: RuStore

### Публикация в RuStore
1. Зайти в [RuStore Developer Console](https://developer.rustore.ru)
2. Создать новое приложение "MagaDrive"
3. Загрузить `MagDrive.apk`
4. Заполнить описание и скриншоты
5. Отправить на модерацию

## 🔧 Environment Variables

### Production
```env
ENVIRONMENT=production
API_BASE_URL=https://your-app.railway.app
MAPTILER_API_KEY=SjhYKAeXJxWy3pPcQc2G
LOG_LEVEL=INFO
```

### Frontend
```env
API_BASE_URL=https://your-app.railway.app
MAPTILER_API_KEY=SjhYKAeXJxWy3pPcQc2G
USE_WS=true
SHOW_PAYMENTS=false
```

## 📊 Мониторинг

### Health Endpoints
- `GET /healthz` - Health check
- `GET /readyz` - Ready check
- `GET /metrics` - Metrics (если включены)

### Логи
```bash
# Railway
railway logs

# Docker локально
docker compose logs -f
```

## 🚨 Troubleshooting

### Проблемы с Railway
1. Проверить переменные окружения
2. Проверить логи: `railway logs`
3. Проверить статус: `railway status`

### Проблемы с APK
1. Проверить подпись
2. Проверить размер (должен быть ~75 МБ)
3. Проверить на эмуляторе

## 📞 Поддержка

- **Backend**: Railway Dashboard
- **Frontend**: RuStore Developer Console
- **Логи**: Railway CLI или Dashboard
