#!/usr/bin/env python3
"""
MagaDrive Ride Service
Управление поездками и событиями
"""

import os
import uuid
import json
import asyncio
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Настройка логирования
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Модели данных
class CreateRideRequest(BaseModel):
    origin: str
    destination: str
    vehicleClass: str
    userId: str

class RideResponse(BaseModel):
    id: str
    userId: str
    origin: str
    destination: str
    vehicleClass: str
    status: str
    createdAt: str
    updatedAt: str
    driverId: Optional[str] = None
    driverName: Optional[str] = None
    driverPhone: Optional[str] = None
    vehicleNumber: Optional[str] = None
    driverRating: Optional[float] = None
    etaSeconds: Optional[int] = None
    distanceMeters: Optional[float] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    cancelReason: Optional[str] = None
    traceId: Optional[str] = None

class CancelRideRequest(BaseModel):
    reason: Optional[str] = None

class ApiResponse(BaseModel):
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    traceId: str

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str

# Конфигурация
ENV = os.getenv("ENV", "dev")
PORT = int(os.getenv("PORT", "7031"))
DB_PATH = os.getenv("DB_URL", "sqlite:////data/ride.db").replace("sqlite:///", "")

# WebSocket соединения
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, ride_id: str):
        await websocket.accept()
        if ride_id not in self.active_connections:
            self.active_connections[ride_id] = []
        self.active_connections[ride_id].append(websocket)
        logger.info("WebSocket connected", ride_id=ride_id, connections=len(self.active_connections[ride_id]))

    def disconnect(self, websocket: WebSocket, ride_id: str):
        if ride_id in self.active_connections:
            self.active_connections[ride_id].remove(websocket)
            if not self.active_connections[ride_id]:
                del self.active_connections[ride_id]
        logger.info("WebSocket disconnected", ride_id=ride_id)

    async def send_personal_message(self, message: str, ride_id: str):
        if ride_id in self.active_connections:
            for connection in self.active_connections[ride_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error("Failed to send message", error=str(e))
                    self.disconnect(connection, ride_id)

manager = ConnectionManager()

# База данных
class RideDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица поездок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rides (
                id TEXT PRIMARY KEY,
                userId TEXT NOT NULL,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                vehicleClass TEXT NOT NULL,
                status TEXT NOT NULL,
                createdAt TEXT NOT NULL,
                updatedAt TEXT NOT NULL,
                driverId TEXT,
                driverName TEXT,
                driverPhone TEXT,
                vehicleNumber TEXT,
                driverRating REAL,
                etaSeconds INTEGER,
                distanceMeters REAL,
                price REAL,
                currency TEXT DEFAULT 'RUB',
                cancelReason TEXT,
                traceId TEXT
            )
        ''')
        
        # Таблица событий поездок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ride_events (
                id TEXT PRIMARY KEY,
                rideId TEXT NOT NULL,
                eventType TEXT NOT NULL,
                eventData TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (rideId) REFERENCES rides (id)
            )
        ''')
        
        # Индексы
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rides_userId ON rides (userId)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rides_status ON rides (status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ride_events_rideId ON ride_events (rideId)')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized", db_path=self.db_path)

    def create_ride(self, ride_data: Dict[str, Any]) -> str:
        """Создание новой поездки"""
        ride_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO rides (
                id, userId, origin, destination, vehicleClass, status,
                createdAt, updatedAt, traceId
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ride_id, ride_data['userId'], ride_data['origin'], ride_data['destination'],
            ride_data['vehicleClass'], 'requested', now, now, ride_data.get('traceId')
        ))
        
        # Создаем событие RIDE_CREATED
        event_id = str(uuid.uuid4())
        event_data = json.dumps({
            'rideId': ride_id,
            'status': 'requested',
            'timestamp': now
        })
        
        cursor.execute('''
            INSERT INTO ride_events (id, rideId, eventType, eventData, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (event_id, ride_id, 'RIDE_CREATED', event_data, now))
        
        conn.commit()
        conn.close()
        
        logger.info("Ride created", ride_id=ride_id, user_id=ride_data['userId'])
        return ride_id

    def get_ride(self, ride_id: str) -> Optional[Dict[str, Any]]:
        """Получение поездки по ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM rides WHERE id = ?', (ride_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        return None

    def update_ride_status(self, ride_id: str, status: str, **kwargs):
        """Обновление статуса поездки"""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Обновляем поездку
        update_fields = ['status = ?, updatedAt = ?']
        update_values = [status, now]
        
        for key, value in kwargs.items():
            if value is not None:
                update_fields.append(f'{key} = ?')
                update_values.append(value)
        
        update_values.append(ride_id)
        cursor.execute(f'UPDATE rides SET {", ".join(update_fields)} WHERE id = ?', update_values)
        
        # Создаем событие
        event_id = str(uuid.uuid4())
        event_data = json.dumps({
            'rideId': ride_id,
            'status': status,
            'timestamp': now,
            **kwargs
        })
        
        cursor.execute('''
            INSERT INTO ride_events (id, rideId, eventType, eventData, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (event_id, ride_id, 'RIDE_STATUS_CHANGED', event_data, now))
        
        conn.commit()
        conn.close()
        
        logger.info("Ride status updated", ride_id=ride_id, status=status)

    def cancel_ride(self, ride_id: str, reason: str):
        """Отмена поездки"""
        self.update_ride_status(ride_id, 'canceled', cancelReason=reason)
        logger.info("Ride canceled", ride_id=ride_id, reason=reason)

# Инициализация базы данных
db = RideDatabase(DB_PATH)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("Starting Ride Service", env=ENV, port=PORT)
    yield
    logger.info("Shutting down Ride Service")

# Создание FastAPI приложения
app = FastAPI(
    title="MagaDrive Ride Service",
    description="Сервис управления поездками",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware для логирования
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    
    trace_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    
    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        trace_id=trace_id
    )
    
    response = await call_next(request)
    
    process_time = (datetime.now() - start_time).total_seconds()
    
    logger.info(
        "Request completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        process_time=process_time,
        trace_id=trace_id
    )
    
    return response

# Health check
@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        service="ride-service"
    )

# Ready check
@app.get("/readyz", response_model=HealthResponse)
async def ready_check():
    try:
        # Проверяем подключение к БД
        conn = sqlite3.connect(DB_PATH)
        conn.close()
        return HealthResponse(
            status="ready",
            timestamp=datetime.now().isoformat(),
            service="ride-service"
        )
    except Exception as e:
        logger.error("Service not ready", error=str(e))
        raise HTTPException(status_code=503, detail="Service not ready")

# Создание поездки
@app.post("/rides", response_model=ApiResponse)
async def create_ride(request: CreateRideRequest, req: Request):
    try:
        trace_id = req.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        ride_data = {
            'userId': request.userId,
            'origin': request.origin,
            'destination': request.destination,
            'vehicleClass': request.vehicleClass,
            'traceId': trace_id
        }
        
        ride_id = db.create_ride(ride_data)
        
        # Получаем созданную поездку
        ride = db.get_ride(ride_id)
        
        # Отправляем событие через WebSocket
        event_data = {
            'type': 'RIDE_CREATED',
            'eventId': str(uuid.uuid4()),
            'data': {
                'rideId': ride_id,
                'status': 'requested',
                'timestamp': datetime.now().isoformat()
            }
        }
        
        await manager.send_personal_message(json.dumps(event_data), ride_id)
        
        # Запускаем симуляцию назначения водителя
        asyncio.create_task(simulate_driver_assignment(ride_id))
        
        return ApiResponse(
            data=ride,
            traceId=trace_id
        )
        
    except Exception as e:
        logger.error("Failed to create ride", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Получение поездки
@app.get("/rides/{ride_id}", response_model=ApiResponse)
async def get_ride(ride_id: str, req: Request):
    try:
        trace_id = req.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        ride = db.get_ride(ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        return ApiResponse(
            data=ride,
            traceId=trace_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get ride", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Отмена поездки
@app.post("/rides/{ride_id}/cancel", response_model=ApiResponse)
async def cancel_ride(ride_id: str, request: CancelRideRequest, req: Request):
    try:
        trace_id = req.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        ride = db.get_ride(ride_id)
        if not ride:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        if ride['status'] not in ['requested', 'searching', 'assigned', 'onTheWay']:
            raise HTTPException(status_code=400, detail="Cannot cancel ride in current status")
        
        db.cancel_ride(ride_id, request.reason or "User canceled")
        
        # Отправляем событие через WebSocket
        event_data = {
            'type': 'RIDE_CANCELED',
            'eventId': str(uuid.uuid4()),
            'data': {
                'rideId': ride_id,
                'status': 'canceled',
                'reason': request.reason or "User canceled",
                'timestamp': datetime.now().isoformat()
            }
        }
        
        await manager.send_personal_message(json.dumps(event_data), ride_id)
        
        return ApiResponse(
            data={'status': 'canceled'},
            traceId=trace_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel ride", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket для событий поездки
@app.websocket("/ws/ride/{ride_id}")
async def websocket_endpoint(websocket: WebSocket, ride_id: str):
    await manager.connect(websocket, ride_id)
    try:
        while True:
            # Ожидаем сообщения от клиента
            data = await websocket.receive_text()
            logger.info("WebSocket message received", ride_id=ride_id, data=data)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, ride_id)

# Симуляция назначения водителя
async def simulate_driver_assignment(ride_id: str):
    """Симуляция назначения водителя через 2-5 секунд"""
    try:
        # Случайная задержка 2-5 секунд
        delay = 2 + (hash(ride_id) % 3)
        await asyncio.sleep(delay)
        
        # Назначаем водителя
        driver_data = {
            'driverId': f'driver_{uuid.uuid4().hex[:8]}',
            'driverName': 'Александр Петров',
            'driverPhone': '+7 (999) 123-45-67',
            'vehicleNumber': 'А 123 БВ 77',
            'driverRating': 4.8,
            'etaSeconds': 300,  # 5 минут
            'distanceMeters': 2500.0
        }
        
        db.update_ride_status(ride_id, 'assigned', **driver_data)
        
        # Отправляем событие DRIVER_ASSIGNED
        event_data = {
            'type': 'DRIVER_ASSIGNED',
            'eventId': str(uuid.uuid4()),
            'data': {
                'rideId': ride_id,
                'status': 'assigned',
                'timestamp': datetime.now().isoformat(),
                **driver_data
            }
        }
        
        await manager.send_personal_message(json.dumps(event_data), ride_id)
        
        # Через 2 секунды отправляем ETA_UPDATE
        await asyncio.sleep(2)
        
        eta_event_data = {
            'type': 'ETA_UPDATE',
            'eventId': str(uuid.uuid4()),
            'data': {
                'rideId': ride_id,
                'etaSeconds': 180,  # 3 минуты
                'distanceMeters': 2000.0,
                'timestamp': datetime.now().isoformat()
            }
        }
        
        await manager.send_personal_message(json.dumps(eta_event_data), ride_id)
        
        logger.info("Driver assignment simulation completed", ride_id=ride_id)
        
    except Exception as e:
        logger.error("Driver assignment simulation failed", error=str(e), ride_id=ride_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
