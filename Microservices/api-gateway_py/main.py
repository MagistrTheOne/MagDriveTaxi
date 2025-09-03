#!/usr/bin/env python3
"""
MagaDrive API Gateway
Единственная публичная точка для всех API запросов
"""

import os
import uuid
import time
import json
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request, Response, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Настройка логирования
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
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

class CancelRideRequest(BaseModel):
    reason: Optional[str] = None

class RouteRequest(BaseModel):
    origin: str
    destination: str

class PricingRequest(BaseModel):
    distanceM: float
    etaSec: int
    class_type: str

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
RIDES_URL = os.getenv("RIDES_URL", "http://ride:7031")
GEO_URL = os.getenv("GEO_URL", "http://geo:7032")
PRICING_URL = os.getenv("PRICING_URL", "http://pricing:7010")

# HTTP клиент
http_client = httpx.AsyncClient(timeout=10.0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("Starting API Gateway", env=ENV)
    yield
    logger.info("Shutting down API Gateway")
    await http_client.aclose()

# Создание FastAPI приложения
app = FastAPI(
    title="MagaDrive API Gateway",
    description="Единая точка входа для всех API запросов",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене ограничить
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware для логирования и trace-id
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware для логирования запросов и добавления trace-id"""
    start_time = time.time()
    
    # Генерируем trace-id если его нет
    trace_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    
    # Логируем начало запроса
    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        trace_id=trace_id,
        user_agent=request.headers.get("user-agent"),
        client_ip=request.client.host if request.client else None
    )
    
    # Добавляем trace-id в заголовки
    request.state.trace_id = trace_id
    
    # Обрабатываем запрос
    response = await call_next(request)
    
    # Вычисляем время выполнения
    process_time = time.time() - start_time
    
    # Добавляем trace-id в ответ
    response.headers["X-Request-Id"] = trace_id
    
    # Логируем завершение запроса
    logger.info(
        "Request completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        trace_id=trace_id,
        duration_ms=round(process_time * 1000, 2)
    )
    
    return response

# Health checks
@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Liveness probe"""
    return HealthResponse(
        status="healthy",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        service="api-gateway"
    )

# API маршруты
@app.post("/rides", response_model=ApiResponse)
async def create_ride(request: CreateRideRequest, req: Request):
    """Создание новой поездки"""
    try:
        trace_id = req.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        # Проксируем запрос в ride service
        ride_response = await http_client.post(
            f"{RIDES_URL}/rides",
            json={
                "origin": request.origin,
                "destination": request.destination,
                "vehicleClass": request.vehicleClass,
                "userId": request.userId
            },
            headers={"X-Request-Id": trace_id}
        )
        
        if ride_response.status_code == 200:
            return ApiResponse(
                data=ride_response.json(),
                traceId=trace_id
            )
        else:
            return ApiResponse(
                error={
                    "code": "RIDE_CREATION_FAILED",
                    "message": "Failed to create ride",
                    "statusCode": ride_response.status_code
                },
                traceId=trace_id
            )
            
    except Exception as e:
        logger.error("Create ride failed", error=str(e))
        return ApiResponse(
            error={
                "code": "INTERNAL_ERROR",
                "message": str(e)
            },
            traceId=trace_id
        )

@app.get("/rides/{ride_id}", response_model=ApiResponse)
async def get_ride(ride_id: str, req: Request):
    """Получение информации о поездке"""
    try:
        trace_id = req.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        ride_response = await http_client.get(
            f"{RIDES_URL}/rides/{ride_id}",
            headers={"X-Request-Id": trace_id}
        )
        
        if ride_response.status_code == 200:
            return ApiResponse(
                data=ride_response.json(),
                traceId=trace_id
            )
        else:
            return ApiResponse(
                error={
                    "code": "RIDE_NOT_FOUND",
                    "message": "Ride not found",
                    "statusCode": ride_response.status_code
                },
                traceId=trace_id
            )
            
    except Exception as e:
        logger.error("Get ride failed", error=str(e))
        return ApiResponse(
            error={
                "code": "INTERNAL_ERROR",
                "message": str(e)
            },
            traceId=trace_id
        )

@app.post("/rides/{ride_id}/cancel", response_model=ApiResponse)
async def cancel_ride(ride_id: str, request: CancelRideRequest, req: Request):
    """Отмена поездки"""
    try:
        trace_id = req.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        cancel_response = await http_client.post(
            f"{RIDES_URL}/rides/{ride_id}/cancel",
            json={"reason": request.reason},
            headers={"X-Request-Id": trace_id}
        )
        
        if cancel_response.status_code == 200:
            return ApiResponse(
                data=cancel_response.json(),
                traceId=trace_id
            )
        else:
            return ApiResponse(
                error={
                    "code": "RIDE_CANCEL_FAILED",
                    "message": "Failed to cancel ride",
                    "statusCode": cancel_response.status_code
                },
                traceId=trace_id
            )
            
    except Exception as e:
        logger.error("Cancel ride failed", error=str(e))
        return ApiResponse(
            error={
                "code": "INTERNAL_ERROR",
                "message": str(e)
            },
            traceId=trace_id
        )

@app.post("/route/eta", response_model=ApiResponse)
async def get_route_eta(request: RouteRequest, req: Request):
    """Получение ETA и расстояния для маршрута"""
    try:
        trace_id = req.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        geo_response = await http_client.post(
            f"{GEO_URL}/route/eta",
            json={
                "origin": request.origin,
                "destination": request.destination
            },
            headers={"X-Request-Id": trace_id}
        )
        
        if geo_response.status_code == 200:
            return ApiResponse(
                data=geo_response.json(),
                traceId=trace_id
            )
        else:
            return ApiResponse(
                error={
                    "code": "ROUTE_CALCULATION_FAILED",
                    "message": "Failed to calculate route",
                    "statusCode": geo_response.status_code
                },
                traceId=trace_id
            )
            
    except Exception as e:
        logger.error("Route ETA failed", error=str(e))
        return ApiResponse(
            error={
                "code": "INTERNAL_ERROR",
                "message": str(e)
            },
            traceId=trace_id
        )

@app.get("/drivers")
async def get_drivers(bbox: str, req: Request):
    """Получение списка водителей в bounding box"""
    try:
        trace_id = req.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        drivers_response = await http_client.get(
            f"{GEO_URL}/drivers?bbox={bbox}",
            headers={"X-Request-Id": trace_id}
        )
        
        if drivers_response.status_code == 200:
            return ApiResponse(
                data=drivers_response.json(),
                traceId=trace_id
            )
        else:
            return ApiResponse(
                error={
                    "code": "DRIVERS_FETCH_FAILED",
                    "message": "Failed to fetch drivers",
                    "statusCode": drivers_response.status_code
                },
                traceId=trace_id
            )
            
    except Exception as e:
        logger.error("Get drivers failed", error=str(e))
        return ApiResponse(
            error={
                "code": "INTERNAL_ERROR",
                "message": str(e)
            },
            traceId=trace_id
        )

@app.post("/price", response_model=ApiResponse)
async def calculate_price(request: PricingRequest, req: Request):
    """Расчет цены поездки"""
    try:
        trace_id = req.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        pricing_response = await http_client.post(
            f"{PRICING_URL}/price",
            json={
                "distanceM": request.distanceM,
                "etaSec": request.etaSec,
                "class": request.class_type
            },
            headers={"X-Request-Id": trace_id}
        )
        
        if pricing_response.status_code == 200:
            return ApiResponse(
                data=pricing_response.json(),
                traceId=trace_id
            )
        else:
            return ApiResponse(
                error={
                    "code": "PRICING_CALCULATION_FAILED",
                    "message": "Failed to calculate price",
                    "statusCode": pricing_response.status_code
                },
                traceId=trace_id
            )
            
    except Exception as e:
        logger.error("Price calculation failed", error=str(e))
        return ApiResponse(
            error={
                "code": "INTERNAL_ERROR",
                "message": str(e)
            },
            traceId=trace_id
        )

# WebSocket endpoint для ретрансляции событий
@app.websocket("/ws/ride/{ride_id}")
async def websocket_ride_events(websocket: WebSocket, ride_id: str):
    """WebSocket для получения событий поездки в реальном времени"""
    await websocket.accept()
    
    try:
        # Подключаемся к ride service WebSocket
        async with httpx.AsyncClient() as client:
            ride_ws_url = f"{RIDES_URL.replace('http', 'ws')}/ws/ride/{ride_id}"
            
            # Проксируем события от ride service к клиенту
            async with client.websocket_connect(ride_ws_url) as ride_ws:
                # Запускаем два потока: один читает от ride service, другой от клиента
                import asyncio
                
                async def forward_from_ride():
                    try:
                        async for message in ride_ws.iter_text():
                            await websocket.send_text(message)
                    except Exception as e:
                        logger.error("Error forwarding from ride service", error=str(e))
                
                async def forward_to_ride():
                    try:
                        async for message in websocket.iter_text():
                            # Клиент может отправлять команды в ride service
                            await ride_ws.send_text(message)
                    except Exception as e:
                        logger.error("Error forwarding to ride service", error=str(e))
                
                # Запускаем оба потока
                await asyncio.gather(
                    forward_from_ride(),
                    forward_to_ride(),
                    return_exceptions=True
                )
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected", ride_id=ride_id)
    except Exception as e:
        logger.error("WebSocket error", error=str(e), ride_id=ride_id)
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass

@app.get("/readyz", response_model=HealthResponse)
async def readiness_check():
    """Readiness probe"""
    # Проверяем доступность зависимых сервисов
    try:
        # Проверяем ride service
        async with httpx.AsyncClient(timeout=2.0) as client:
            ride_response = await client.get(f"{RIDES_URL}/healthz")
            if ride_response.status_code != 200:
                raise HTTPException(status_code=503, detail="Ride service not ready")
        
        # Проверяем geo service
        async with httpx.AsyncClient(timeout=2.0) as client:
            geo_response = await client.get(f"{GEO_URL}/healthz")
            if geo_response.status_code != 200:
                raise HTTPException(status_code=503, detail="Geo service not ready")
        
        # Проверяем pricing service
        async with httpx.AsyncClient(timeout=2.0) as client:
            pricing_response = await client.get(f"{PRICING_URL}/healthz")
            if pricing_response.status_code != 200:
                raise HTTPException(status_code=503, detail="Pricing service not ready")
        
        return HealthResponse(
            status="ready",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            service="api-gateway"
        )
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service not ready")

# API v1 роуты
@app.get("/v1/health", response_model=ApiResponse)
async def api_health():
    """API health check"""
    return ApiResponse(
        data={"status": "healthy", "service": "api-gateway"},
        error=None,
        traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
    )

# Проксирование к ride service
@app.post("/v1/rides")
async def create_ride(request: Request):
    """Создание новой поездки"""
    try:
        # Получаем тело запроса
        body = await request.json()
        
        # Проверяем обязательные заголовки
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            raise HTTPException(status_code=400, detail="Idempotency-Key header required")
        
        # Проксируем запрос к ride service
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{RIDES_URL}/rides",
                json=body,
                headers={"Idempotency-Key": idempotency_key}
            )
            
            if response.status_code == 200:
                return JSONResponse(
                    content=ApiResponse(
                        data=response.json(),
                        error=None,
                        traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
                    ).dict(),
                    status_code=200,
                    headers={"X-Request-Id": getattr(request.state, "trace_id", str(uuid.uuid4()))}
                )
            else:
                raise HTTPException(status_code=response.status_code, detail="Ride service error")
                
    except Exception as e:
        logger.error("Create ride failed", error=str(e))
        return JSONResponse(
            content=ApiResponse(
                data=None,
                error={"code": "INTERNAL_ERROR", "message": str(e)},
                traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
            ).dict(),
            status_code=500,
            headers={"X-Request-Id": getattr(request.state, "trace_id", str(uuid.uuid4()))}
        )

@app.get("/v1/rides/{ride_id}")
async def get_ride(ride_id: str, request: Request):
    """Получение информации о поездке"""
    try:
        # Проксируем запрос к ride service
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{RIDES_URL}/rides/{ride_id}")
            
            if response.status_code == 200:
                return JSONResponse(
                    content=ApiResponse(
                        data=response.json(),
                        error=None,
                        traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
                    ).dict(),
                    status_code=200,
                    headers={"X-Request-Id": getattr(request.state, "trace_id", str(uuid.uuid4()))}
                )
            elif response.status_code == 404:
                return JSONResponse(
                    content=ApiResponse(
                        data=None,
                        error={"code": "RIDE_NOT_FOUND", "message": "Поездка не найдена"},
                        traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
                    ).dict(),
                    status_code=404,
                    headers={"X-Request-Id": getattr(request.state, "trace_id", str(uuid.uuid4()))}
                )
            else:
                raise HTTPException(status_code=response.status_code, detail="Ride service error")
                
    except Exception as e:
        logger.error("Get ride failed", error=str(e))
        return JSONResponse(
            content=ApiResponse(
                data=None,
                error={"code": "INTERNAL_ERROR", "message": str(e)},
                traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
            ).dict(),
            status_code=500,
            headers={"X-Request-Id": getattr(request.state, "trace_id", str(uuid.uuid4()))}
        )

# Проксирование к geo service
@app.get("/v1/drivers")
async def get_drivers(bbox: str, request: Request):
    """Поиск водителей в bounding box"""
    try:
        # Проксируем запрос к geo service
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{GEO_URL}/drivers?bbox={bbox}")
            
            if response.status_code == 200:
                return JSONResponse(
                    content=ApiResponse(
                        data=response.json(),
                        error=None,
                        traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
                    ).dict(),
                    status_code=200,
                    headers={"X-Request-Id": getattr(request.state, "trace_id", str(uuid.uuid4()))}
                )
            else:
                raise HTTPException(status_code=response.status_code, detail="Geo service error")
                
    except Exception as e:
        logger.error("Get drivers failed", error=str(e))
        return JSONResponse(
            content=ApiResponse(
                data=None,
                error={"code": "INTERNAL_ERROR", "message": str(e)},
                traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
            ).dict(),
            status_code=500,
            headers={"X-Request-Id": getattr(request.state, "trace_id", str(uuid.uuid4()))}
        )

@app.post("/v1/rides/{ride_id}/cancel")
async def cancel_ride(ride_id: str, request: Request):
    """Отмена поездки"""
    try:
        # Проксируем запрос к ride service
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{RIDES_URL}/rides/{ride_id}/cancel")
            
            if response.status_code == 200:
                return JSONResponse(
                    content=ApiResponse(
                        data=response.json(),
                        error=None,
                        traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
                    ).dict(),
                    status_code=200,
                    headers={"X-Request-Id": getattr(request.state, "trace_id", str(uuid.uuid4()))}
                )
            elif response.status_code == 404:
                return JSONResponse(
                    content=ApiResponse(
                        data=None,
                        error={"code": "RIDE_NOT_FOUND", "message": "Поездка не найдена"},
                        traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
                    ).dict(),
                    status_code=404,
                    headers={"X-Request-Id": getattr(request.state, "trace_id", str(uuid.uuid4()))}
                )
            else:
                raise HTTPException(status_code=response.status_code, detail="Ride service error")
                
    except Exception as e:
        logger.error("Cancel ride failed", error=str(e))
        return JSONResponse(
            content=ApiResponse(
                data=None,
                error={"code": "INTERNAL_ERROR", "message": str(e)},
                traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
            ).dict(),
            status_code=500,
            headers={"X-Request-Id": getattr(request.state, "trace_id", str(uuid.uuid4()))}
        )

@app.post("/v1/route/eta")
async def calculate_route_eta(request: Request):
    """Расчет маршрута и ETA"""
    try:
        # Получаем тело запроса
        body = await request.json()
        
        # Проксируем запрос к geo service
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{GEO_URL}/route/eta", json=body)
            
            if response.status_code == 200:
                return JSONResponse(
                    content=ApiResponse(
                        data=response.json(),
                        error=None,
                        traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
                    ).dict(),
                    status_code=200,
                    headers={"X-Request-Id": getattr(request.state, "trace_id", str(uuid.uuid4()))}
                )
            else:
                raise HTTPException(status_code=response.status_code, detail="Geo service error")
                
    except Exception as e:
        logger.error("Calculate route ETA failed", error=str(e))
        return JSONResponse(
            content=ApiResponse(
                data=None,
                error={"code": "INTERNAL_ERROR", "message": str(e)},
                traceId=getattr(request.state, "trace_id", str(uuid.uuid4()))
            ).dict(),
            status_code=500,
            headers={"X-Request-Id": getattr(request.state, "trace_id", str(uuid.uuid4()))}
        )

# WebSocket для событий поездки
@app.websocket("/ws/ride/{ride_id}")
async def websocket_ride_events(websocket: WebSocket, ride_id: str):
    """WebSocket для получения событий поездки в реальном времени"""
    await websocket.accept()
    logger.info("WebSocket connection established", ride_id=ride_id, trace_id=str(uuid.uuid4()))
    
    try:
        # В T8-T10 просто ретранслируем события от ride service
        # В будущем здесь будет полноценная подписка на события
        
        # Отправляем приветственное сообщение
        await websocket.send_text(json.dumps({
            "type": "event",
            "ts": time.time(),
            "payload": {
                "eventType": "CONNECTED",
                "data": {
                    "rideId": ride_id,
                    "message": "WebSocket подключен"
                }
            }
        }))
        
        # Держим соединение открытым
        while True:
            try:
                # Проверяем соединение каждые 30 секунд
                await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected", ride_id=ride_id)
                break
            except Exception as e:
                logger.error("WebSocket error", ride_id=ride_id, error=str(e))
                break
                
    except Exception as e:
        logger.error("WebSocket connection error", ride_id=ride_id, error=str(e))
    finally:
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=ENV == "dev"
    )
