#!/usr/bin/env python3
"""
MagaDrive Ride Service - T8-T10
Управление поездками и генерация событий
"""

import asyncio
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "traceId": "%(traceId)s"}',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class CustomFormatter(logging.Formatter):
    def format(self, record):
        record.traceId = getattr(record, 'traceId', 'unknown')
        return super().format(record)

logger = logging.getLogger(__name__)
logger.handlers[0].setFormatter(CustomFormatter())

# Конфигурация
DB_PATH = os.getenv('DB_PATH', 'ride_service.db')
GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://api-gateway:8000')

# HTTP клиент для отправки событий в gateway
http_client = httpx.AsyncClient(timeout=5.0)

app = FastAPI(
    title="MagaDrive Ride Service",
    description="Сервис управления поездками T8-T10",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели данных
class RideCreateRequest(BaseModel):
    origin: str
    destination: str
    vehicleClass: str
    userId: Optional[str] = None
    originLat: Optional[float] = None
    originLng: Optional[float] = None
    destLat: Optional[float] = None
    destLng: Optional[float] = None

class RideCancelRequest(BaseModel):
    reason: Optional[str] = None

class RideEvent(BaseModel):
    id: str
    ride_id: str
    event_type: str
    event_data: Dict[str, Any]
    created_at: datetime

# Инициализация базы данных
def init_database():
    """Инициализация SQLite базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица поездок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rides (
            id TEXT PRIMARY KEY,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            vehicle_class TEXT NOT NULL,
            user_id TEXT NOT NULL,
            origin_lat REAL,
            origin_lng REAL,
            dest_lat REAL,
            dest_lng REAL,
            status TEXT NOT NULL DEFAULT 'requested',
            driver_id TEXT,
            driver_name TEXT,
            driver_phone TEXT,
            vehicle_number TEXT,
            driver_rating REAL,
            driver_lat REAL,
            driver_lng REAL,
            eta_seconds INTEGER,
            distance_meters REAL,
            price REAL,
            currency TEXT DEFAULT 'RUB',
            cancel_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Индексы для оптимизации
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rides_user_id ON rides(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rides_status ON rides(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rides_created_at ON rides(created_at)')
    
    # Таблица событий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ride_events (
            id TEXT PRIMARY KEY,
            ride_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ride_id) REFERENCES rides(id)
        )
    ''')
    
    # Индексы для событий
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_ride_id ON ride_events(ride_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_type ON ride_events(event_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_created_at ON ride_events(created_at)')
    
    conn.commit()
    conn.close()
    
    logger.info("Database initialized")

# Инициализация при старте
init_database()

# Middleware для добавления traceId
@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    trace_id = request.headers.get('X-Request-Id', str(uuid.uuid4()))
    request.state.trace_id = trace_id
    
    logger.info(f"Request: {request.method} {request.url.path}", extra={'traceId': trace_id})
    
    response = await call_next(request)
    response.headers['X-Request-Id'] = trace_id
    return response

# Health check endpoints
@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/readyz")
async def ready_check():
    """Ready check endpoint"""
    try:
        # Проверяем доступность базы данных
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logger.error(f"Ready check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)}
        )

# Функция для отправки событий
async def emit_ride_event(ride_id: str, event_type: str, event_data: Dict[str, Any], trace_id: str):
    """Отправка события поездки"""
    event_id = str(uuid.uuid4())
    
    # Сохраняем событие в базу
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO ride_events (id, ride_id, event_type, event_data, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (event_id, ride_id, event_type, json.dumps(event_data), datetime.utcnow()))
    
    conn.commit()
    conn.close()
    
    # Отправляем событие в gateway для WebSocket трансляции
    try:
        event_payload = {
            "type": event_type,
            "data": {
                "rideId": ride_id,
                **event_data
            },
            "eventId": event_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await http_client.post(
            f"{GATEWAY_URL}/internal/ride-events",
            json=event_payload,
            headers={'X-Request-Id': trace_id}
        )
        
        logger.info(f"Event {event_type} emitted for ride {ride_id}", extra={'traceId': trace_id})
        
    except Exception as e:
        logger.error(f"Failed to emit event {event_type}: {e}", extra={'traceId': trace_id})

# REST API endpoints
@app.post("/rides")
async def create_ride(request: RideCreateRequest, http_request: Request):
    """Создание новой поездки"""
    trace_id = http_request.state.trace_id
    
    try:
        ride_id = str(uuid.uuid4())
        user_id = request.userId or 'dev-user'
        
        # Сохраняем поездку в базу
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO rides (
                id, origin, destination, vehicle_class, user_id,
                origin_lat, origin_lng, dest_lat, dest_lng,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ride_id, request.origin, request.destination, request.vehicleClass, user_id,
            request.originLat, request.originLng, request.destLat, request.destLng,
            'requested', datetime.utcnow(), datetime.utcnow()
        ))
        
        conn.commit()
        conn.close()
        
        # Эмитим событие RIDE_CREATED
        await emit_ride_event(ride_id, 'RIDE_CREATED', {
            "origin": request.origin,
            "destination": request.destination,
            "vehicleClass": request.vehicleClass,
            "userId": user_id
        }, trace_id)
        
        # Запускаем фоновый процесс назначения водителя
        asyncio.create_task(assign_driver_simulation(ride_id, trace_id))
        
        # Возвращаем информацию о поездке
        ride_data = {
            "id": ride_id,
            "origin": request.origin,
            "destination": request.destination,
            "vehicleClass": request.vehicleClass,
            "userId": user_id,
            "status": "requested",
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Ride {ride_id} created", extra={'traceId': trace_id})
        
        return {
            "data": ride_data,
            "error": None,
            "traceId": trace_id
        }
        
    except Exception as e:
        logger.error(f"Failed to create ride: {e}", extra={'traceId': trace_id})
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "error": {"code": "RIDE_CREATION_FAILED", "message": str(e)},
                "traceId": trace_id
            }
        )

@app.get("/rides/{ride_id}")
async def get_ride(ride_id: str, http_request: Request):
    """Получение информации о поездке"""
    trace_id = http_request.state.trace_id
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM rides WHERE id = ?
        ''', (ride_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return JSONResponse(
                status_code=404,
                content={
                    "data": None,
                    "error": {"code": "RIDE_NOT_FOUND", "message": "Ride not found"},
                    "traceId": trace_id
                }
            )
        
        # Преобразуем результат в словарь
        columns = [description[0] for description in cursor.description]
        ride_dict = dict(zip(columns, row))
        
        # Форматируем ответ
        ride_data = {
            "id": ride_dict["id"],
            "origin": ride_dict["origin"],
            "destination": ride_dict["destination"],
            "vehicleClass": ride_dict["vehicle_class"],
            "userId": ride_dict["user_id"],
            "status": ride_dict["status"],
            "originLat": ride_dict["origin_lat"],
            "originLng": ride_dict["origin_lng"],
            "destLat": ride_dict["dest_lat"],
            "destLng": ride_dict["dest_lng"],
            "driverId": ride_dict["driver_id"],
            "driverName": ride_dict["driver_name"],
            "driverPhone": ride_dict["driver_phone"],
            "vehicleNumber": ride_dict["vehicle_number"],
            "driverRating": ride_dict["driver_rating"],
            "driverLat": ride_dict["driver_lat"],
            "driverLng": ride_dict["driver_lng"],
            "etaSeconds": ride_dict["eta_seconds"],
            "distanceMeters": ride_dict["distance_meters"],
            "price": ride_dict["price"],
            "currency": ride_dict["currency"],
            "cancelReason": ride_dict["cancel_reason"],
            "createdAt": ride_dict["created_at"],
            "updatedAt": ride_dict["updated_at"]
        }
        
        return {
            "data": ride_data,
            "error": None,
            "traceId": trace_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get ride {ride_id}: {e}", extra={'traceId': trace_id})
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "error": {"code": "RIDE_FETCH_FAILED", "message": str(e)},
                "traceId": trace_id
            }
        )

@app.post("/rides/{ride_id}/cancel")
async def cancel_ride(ride_id: str, request: RideCancelRequest, http_request: Request):
    """Отмена поездки"""
    trace_id = http_request.state.trace_id
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем существование поездки
        cursor.execute('SELECT status FROM rides WHERE id = ?', (ride_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return JSONResponse(
                status_code=404,
                content={
                    "data": None,
                    "error": {"code": "RIDE_NOT_FOUND", "message": "Ride not found"},
                    "traceId": trace_id
                }
            )
        
        current_status = row[0]
        if current_status in ['completed', 'canceled']:
            conn.close()
            return JSONResponse(
                status_code=400,
                content={
                    "data": None,
                    "error": {"code": "RIDE_ALREADY_FINISHED", "message": f"Ride already {current_status}"},
                    "traceId": trace_id
                }
            )
        
        # Обновляем статус поездки
        reason = request.reason or 'User canceled'
        cursor.execute('''
            UPDATE rides 
            SET status = ?, cancel_reason = ?, updated_at = ?
            WHERE id = ?
        ''', ('canceled', reason, datetime.utcnow(), ride_id))
        
        conn.commit()
        conn.close()
        
        # Эмитим событие RIDE_CANCELED
        await emit_ride_event(ride_id, 'RIDE_CANCELED', {
            "reason": reason,
            "canceledAt": datetime.utcnow().isoformat()
        }, trace_id)
        
        logger.info(f"Ride {ride_id} canceled: {reason}", extra={'traceId': trace_id})
        
        return {
            "data": {"status": "canceled", "reason": reason},
            "error": None,
            "traceId": trace_id
        }
        
    except Exception as e:
        logger.error(f"Failed to cancel ride {ride_id}: {e}", extra={'traceId': trace_id})
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "error": {"code": "RIDE_CANCEL_FAILED", "message": str(e)},
                "traceId": trace_id
            }
        )

@app.post("/rides/{ride_id}/complete")
async def complete_ride(ride_id: str, http_request: Request):
    """Завершение поездки"""
    trace_id = http_request.state.trace_id
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем существование поездки
        cursor.execute('SELECT status FROM rides WHERE id = ?', (ride_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return JSONResponse(
                status_code=404,
                content={
                    "data": None,
                    "error": {"code": "RIDE_NOT_FOUND", "message": "Ride not found"},
                    "traceId": trace_id
                }
            )
        
        # Обновляем статус поездки
        cursor.execute('''
            UPDATE rides 
            SET status = ?, updated_at = ?
            WHERE id = ?
        ''', ('completed', datetime.utcnow(), ride_id))
        
        conn.commit()
        conn.close()
        
        # Эмитим событие RIDE_COMPLETED
        await emit_ride_event(ride_id, 'RIDE_COMPLETED', {
            "completedAt": datetime.utcnow().isoformat()
        }, trace_id)
        
        logger.info(f"Ride {ride_id} completed", extra={'traceId': trace_id})
        
        return {
            "data": {"status": "completed"},
            "error": None,
            "traceId": trace_id
        }
        
    except Exception as e:
        logger.error(f"Failed to complete ride {ride_id}: {e}", extra={'traceId': trace_id})
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "error": {"code": "RIDE_COMPLETE_FAILED", "message": str(e)},
                "traceId": trace_id
            }
        )

# Заглушка назначения водителя
async def assign_driver_simulation(ride_id: str, trace_id: str):
    """Симуляция назначения водителя с таймером 2-5 секунд"""
    try:
        # Ждем 2-5 секунд
        import random
        delay = random.randint(2, 5)
        await asyncio.sleep(delay)
        
        # Генерируем данные водителя
        driver_data = {
            "driverId": f"driver_{random.randint(1000, 9999)}",
            "driverName": f"Водитель {random.choice(['Алексей', 'Дмитрий', 'Сергей', 'Андрей'])}",
            "driverPhone": f"+7 (999) {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}",
            "vehicleNumber": f"{random.choice(['А', 'В', 'Е', 'К', 'М', 'Н', 'О', 'Р', 'С', 'Т', 'У', 'Х'])}{random.randint(100, 999)}{random.choice(['АА', 'ВВ', 'ЕЕ', 'КК', 'ММ', 'НН', 'ОО', 'РР', 'СС', 'ТТ'])}77",
            "driverRating": round(random.uniform(4.2, 5.0), 1),
            "driverLat": 55.7558 + random.uniform(-0.01, 0.01),
            "driverLng": 37.6176 + random.uniform(-0.01, 0.01)
        }
        
        # Обновляем поездку в базе
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE rides 
            SET status = ?, driver_id = ?, driver_name = ?, driver_phone = ?,
                vehicle_number = ?, driver_rating = ?, driver_lat = ?, driver_lng = ?,
                eta_seconds = ?, updated_at = ?
            WHERE id = ?
        ''', (
            'assigned',
            driver_data["driverId"],
            driver_data["driverName"],
            driver_data["driverPhone"],
            driver_data["vehicleNumber"],
            driver_data["driverRating"],
            driver_data["driverLat"],
            driver_data["driverLng"],
            random.randint(300, 900),  # 5-15 минут ETA
            datetime.utcnow(),
            ride_id
        ))
        
        conn.commit()
        conn.close()
        
        # Эмитим событие DRIVER_ASSIGNED
        await emit_ride_event(ride_id, 'DRIVER_ASSIGNED', driver_data, trace_id)
        
        # Ждем еще немного и отправляем ETA_UPDATE
        await asyncio.sleep(2)
        await emit_ride_event(ride_id, 'ETA_UPDATE', {
            "etaSeconds": random.randint(300, 900),
            "distanceMeters": random.randint(1000, 5000)
        }, trace_id)
        
        # Симулируем движение водителя
        asyncio.create_task(simulate_driver_movement(ride_id, driver_data["driverLat"], driver_data["driverLng"], trace_id))
        
    except Exception as e:
        logger.error(f"Driver assignment simulation failed for ride {ride_id}: {e}", extra={'traceId': trace_id})

# Симуляция движения водителя
async def simulate_driver_movement(ride_id: str, start_lat: float, start_lng: float, trace_id: str):
    """Симуляция движения водителя к пассажиру"""
    try:
        import random
        current_lat = start_lat
        current_lng = start_lng
        
        for i in range(10):  # 10 обновлений местоположения
            await asyncio.sleep(random.randint(5, 15))  # Каждые 5-15 секунд
            
            # Небольшое движение в сторону пассажира
            current_lat += random.uniform(-0.001, 0.001)
            current_lng += random.uniform(-0.001, 0.001)
            
            # Обновляем в базе
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE rides 
                SET driver_lat = ?, driver_lng = ?, updated_at = ?
                WHERE id = ?
            ''', (current_lat, current_lng, datetime.utcnow(), ride_id))
            
            conn.commit()
            conn.close()
            
            # Эмитим событие LOCATION_UPDATE
            await emit_ride_event(ride_id, 'LOCATION_UPDATE', {
                "driverLat": current_lat,
                "driverLng": current_lng
            }, trace_id)
            
    except Exception as e:
        logger.error(f"Driver movement simulation failed for ride {ride_id}: {e}", extra={'traceId': trace_id})

# Функция для отправки событий (вынесена отдельно)
async def emit_ride_event(ride_id: str, event_type: str, event_data: Dict[str, Any], trace_id: str):
    """Отправка события поездки"""
    event_id = str(uuid.uuid4())
    
    # Сохраняем событие в базу
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO ride_events (id, ride_id, event_type, event_data, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (event_id, ride_id, event_type, json.dumps(event_data), datetime.utcnow()))
    
    conn.commit()
    conn.close()
    
    # Отправляем событие в gateway для WebSocket трансляции
    try:
        event_payload = {
            "type": event_type,
            "data": {
                "rideId": ride_id,
                **event_data
            },
            "eventId": event_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await http_client.post(
            f"{GATEWAY_URL}/internal/ride-events",
            json=event_payload,
            headers={'X-Request-Id': trace_id}
        )
        
        logger.info(f"Event {event_type} emitted for ride {ride_id}", extra={'traceId': trace_id})
        
    except Exception as e:
        logger.error(f"Failed to emit event {event_type}: {e}", extra={'traceId': trace_id})

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
