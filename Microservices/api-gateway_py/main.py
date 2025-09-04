#!/usr/bin/env python3
"""
MagaDrive API Gateway - T8-T10
REST маршруты и WebSocket ретранслятор для микросервисов
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
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
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8080')
RIDE_SERVICE_URL = os.getenv('RIDE_SERVICE_URL', 'http://ride-service:8001')
GEO_SERVICE_URL = os.getenv('GEO_SERVICE_URL', 'http://geo-service:8002')
PRICING_SERVICE_URL = os.getenv('PRICING_SERVICE_URL', 'http://pricing-service:8003')

# HTTP клиент
http_client = httpx.AsyncClient(timeout=10.0)

# WebSocket соединения
active_connections: Dict[str, WebSocket] = {}

app = FastAPI(
    title="MagaDrive API Gateway",
    description="API Gateway для микросервисов T8-T10",
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

class RouteEtaRequest(BaseModel):
    originLat: float
    originLng: float
    destLat: float
    destLng: float

class DriversRequest(BaseModel):
    lat: float
    lng: float
    radius: Optional[float] = 5000

# Middleware для добавления traceId
@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    trace_id = request.headers.get('X-Request-Id', str(uuid.uuid4()))
    request.state.trace_id = trace_id
    
    # Добавляем traceId в логи
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
        # Проверяем доступность основных сервисов
        services_status = {}
        
        # Ride service
        try:
            response = await http_client.get(f"{RIDE_SERVICE_URL}/healthz")
            services_status["ride_service"] = response.status_code == 200
        except:
            services_status["ride_service"] = False
        
        # Geo service
        try:
            response = await http_client.get(f"{GEO_SERVICE_URL}/healthz")
            services_status["geo_service"] = response.status_code == 200
        except:
            services_status["geo_service"] = False
        
        # Pricing service
        try:
            response = await http_client.get(f"{PRICING_SERVICE_URL}/healthz")
            services_status["pricing_service"] = response.status_code == 200
        except:
            services_status["pricing_service"] = False
        
        all_ready = all(services_status.values())
        
        if all_ready:
            return {"status": "ready", "services": services_status}
        else:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "services": services_status}
            )
            
    except Exception as e:
        logger.error(f"Ready check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": str(e)}
        )

# REST API маршруты
@app.post("/v1/rides")
async def create_ride(request: RideCreateRequest, http_request: Request):
    """Создание новой поездки"""
    trace_id = http_request.state.trace_id
    
    try:
        # Проксируем запрос в ride service
        headers = {
            'X-Request-Id': trace_id,
            'Content-Type': 'application/json'
        }
        
        # Добавляем Idempotency-Key если есть
        idempotency_key = http_request.headers.get('Idempotency-Key')
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key
        
        response = await http_client.post(
            f"{RIDE_SERVICE_URL}/rides",
            json=request.dict(),
            headers=headers
        )
        
        if response.status_code == 200:
            ride_data = response.json()
            logger.info(f"Ride created: {ride_data.get('id', 'unknown')}", extra={'traceId': trace_id})
            
            return {
                "data": ride_data,
                "error": None,
                "traceId": trace_id
            }
        else:
            error_data = response.json() if response.content else {"message": "Unknown error"}
            logger.error(f"Failed to create ride: {error_data}", extra={'traceId': trace_id})
            
            return JSONResponse(
                status_code=response.status_code,
                content={
                    "data": None,
                    "error": error_data,
                    "traceId": trace_id
                }
            )
            
    except Exception as e:
        logger.error(f"Create ride error: {e}", extra={'traceId': trace_id})
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "error": {"code": "INTERNAL_ERROR", "message": str(e)},
                "traceId": trace_id
            }
        )

@app.get("/v1/rides/{ride_id}")
async def get_ride(ride_id: str, http_request: Request):
    """Получение информации о поездке"""
    trace_id = http_request.state.trace_id
    
    try:
        response = await http_client.get(
            f"{RIDE_SERVICE_URL}/rides/{ride_id}",
            headers={'X-Request-Id': trace_id}
        )
        
        if response.status_code == 200:
            ride_data = response.json()
            return {
                "data": ride_data,
                "error": None,
                "traceId": trace_id
            }
        else:
            error_data = response.json() if response.content else {"message": "Ride not found"}
            return JSONResponse(
                status_code=response.status_code,
                content={
                    "data": None,
                    "error": error_data,
                    "traceId": trace_id
                }
            )
            
    except Exception as e:
        logger.error(f"Get ride error: {e}", extra={'traceId': trace_id})
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "error": {"code": "INTERNAL_ERROR", "message": str(e)},
                "traceId": trace_id
            }
        )

@app.post("/v1/rides/{ride_id}/cancel")
async def cancel_ride(ride_id: str, request: RideCancelRequest, http_request: Request):
    """Отмена поездки"""
    trace_id = http_request.state.trace_id
    
    try:
        headers = {
            'X-Request-Id': trace_id,
            'Content-Type': 'application/json'
        }
        
        # Добавляем Idempotency-Key если есть
        idempotency_key = http_request.headers.get('Idempotency-Key')
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key
        
        response = await http_client.post(
            f"{RIDE_SERVICE_URL}/rides/{ride_id}/cancel",
            json=request.dict(),
            headers=headers
        )
        
        if response.status_code == 200:
            logger.info(f"Ride {ride_id} canceled", extra={'traceId': trace_id})
            return {
                "data": {"status": "canceled"},
                "error": None,
                "traceId": trace_id
            }
        else:
            error_data = response.json() if response.content else {"message": "Failed to cancel ride"}
            return JSONResponse(
                status_code=response.status_code,
                content={
                    "data": None,
                    "error": error_data,
                    "traceId": trace_id
                }
            )
            
    except Exception as e:
        logger.error(f"Cancel ride error: {e}", extra={'traceId': trace_id})
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "error": {"code": "INTERNAL_ERROR", "message": str(e)},
                "traceId": trace_id
            }
        )

@app.post("/v1/route/eta")
async def get_route_eta(request: RouteEtaRequest, http_request: Request):
    """Получение ETA и расстояния маршрута"""
    trace_id = http_request.state.trace_id
    
    try:
        response = await http_client.post(
            f"{GEO_SERVICE_URL}/route/eta",
            json=request.dict(),
            headers={'X-Request-Id': trace_id}
        )
        
        if response.status_code == 200:
            route_data = response.json()
            return {
                "data": route_data,
                "error": None,
                "traceId": trace_id
            }
        else:
            error_data = response.json() if response.content else {"message": "Failed to get route ETA"}
            return JSONResponse(
                status_code=response.status_code,
                content={
                    "data": None,
                    "error": error_data,
                    "traceId": trace_id
                }
            )
            
    except Exception as e:
        logger.error(f"Get route ETA error: {e}", extra={'traceId': trace_id})
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "error": {"code": "INTERNAL_ERROR", "message": str(e)},
                "traceId": trace_id
            }
        )

@app.get("/v1/drivers")
async def get_available_drivers(
    lat: float,
    lng: float,
    radius: float = 5000,
    http_request: Request = None
):
    """Получение доступных водителей в радиусе"""
    trace_id = getattr(http_request.state, 'trace_id', str(uuid.uuid4())) if http_request else str(uuid.uuid4())
    
    try:
        response = await http_client.get(
            f"{GEO_SERVICE_URL}/drivers",
            params={"lat": lat, "lng": lng, "radius": radius},
            headers={'X-Request-Id': trace_id}
        )
        
        if response.status_code == 200:
            drivers_data = response.json()
            return {
                "data": drivers_data,
                "error": None,
                "traceId": trace_id
            }
        else:
            error_data = response.json() if response.content else {"message": "Failed to get drivers"}
            return JSONResponse(
                status_code=response.status_code,
                content={
                    "data": None,
                    "error": error_data,
                    "traceId": trace_id
                }
            )
            
    except Exception as e:
        logger.error(f"Get drivers error: {e}", extra={'traceId': trace_id})
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "error": {"code": "INTERNAL_ERROR", "message": str(e)},
                "traceId": trace_id
            }
        )

# WebSocket endpoint для событий поездки
@app.websocket("/ws/ride/{ride_id}")
async def websocket_ride_events(websocket: WebSocket, ride_id: str):
    """WebSocket для получения событий поездки в реальном времени"""
    await websocket.accept()
    
    connection_id = str(uuid.uuid4())
    active_connections[connection_id] = websocket
    
    logger.info(f"WebSocket connected for ride {ride_id}", extra={'traceId': connection_id})
    
    try:
        # Подписываемся на события ride service
        async with httpx.AsyncClient() as client:
            # Отправляем событие подключения
            await websocket.send_text(json.dumps({
                "type": "CONNECTED",
                "data": {"rideId": ride_id, "message": "Connected to ride events"},
                "eventId": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat()
            }))
            
            # Основной цикл WebSocket
            while True:
                try:
                    # Проверяем соединение
                    await websocket.receive_text()
                    
                    # В T8-T10 просто держим соединение открытым
                    # События будут приходить от ride service через HTTP
                    
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected for ride {ride_id}", extra={'traceId': connection_id})
                    break
                    
    except Exception as e:
        logger.error(f"WebSocket error for ride {ride_id}: {e}", extra={'traceId': connection_id})
    finally:
        # Очищаем соединение
        if connection_id in active_connections:
            del active_connections[connection_id]
        await websocket.close()

# Функция для отправки событий всем подключенным клиентам
async def broadcast_ride_event(ride_id: str, event_data: Dict[str, Any]):
    """Отправка события всем подключенным WebSocket клиентам"""
    event_message = {
        "type": event_data.get("type", "UNKNOWN"),
        "data": event_data.get("data", {}),
        "eventId": event_data.get("eventId", str(uuid.uuid4())),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Находим все соединения для данной поездки
    connections_to_remove = []
    
    for conn_id, websocket in active_connections.items():
        try:
            await websocket.send_text(json.dumps(event_message))
        except Exception as e:
            logger.error(f"Failed to send event to connection {conn_id}: {e}")
            connections_to_remove.append(conn_id)
    
    # Удаляем неработающие соединения
    for conn_id in connections_to_remove:
        if conn_id in active_connections:
            del active_connections[conn_id]

# Endpoint для получения событий от ride service
@app.post("/internal/ride-events")
async def receive_ride_event(event_data: Dict[str, Any], http_request: Request):
    """Внутренний endpoint для получения событий от ride service"""
    trace_id = http_request.state.trace_id
    ride_id = event_data.get("data", {}).get("rideId")
    
    if not ride_id:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing rideId in event data"}
        )
    
    try:
        # Отправляем событие всем подключенным WebSocket клиентам
        await broadcast_ride_event(ride_id, event_data)
        
        logger.info(f"Ride event broadcasted: {event_data.get('type')} for ride {ride_id}", extra={'traceId': trace_id})
        
        return {"status": "event_sent"}
        
    except Exception as e:
        logger.error(f"Failed to broadcast ride event: {e}", extra={'traceId': trace_id})
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
