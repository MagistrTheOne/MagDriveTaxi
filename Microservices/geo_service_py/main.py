#!/usr/bin/env python3
"""
MagaDrive Geo Service
Геолокация, маршруты и водители
"""

import os
import uuid
import json
import asyncio
import random
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request, HTTPException
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
class RouteRequest(BaseModel):
    origin: str
    destination: str

class RouteResponse(BaseModel):
    etaSeconds: int
    distanceMeters: float

class DriverLocation(BaseModel):
    id: str
    latitude: float
    longitude: float
    heading: float
    status: str
    lastUpdate: str

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
PORT = int(os.getenv("PORT", "7032"))
MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY", "")
CACHE_TTL_SEC = int(os.getenv("CACHE_TTL_SEC", "600"))

# HTTP клиент
http_client = httpx.AsyncClient(timeout=10.0)

# Кэш маршрутов
route_cache: Dict[str, Dict[str, Any]] = {}

# Заглушка водителей
mock_drivers: List[Dict[str, Any]] = []

def init_mock_drivers():
    """Инициализация заглушки водителей"""
    global mock_drivers
    
    # Создаем 10 водителей в центре Москвы
    for i in range(10):
        mock_drivers.append({
            'id': f'driver_{i:03d}',
            'latitude': 55.7558 + (random.random() - 0.5) * 0.01,  # ±5 км
            'longitude': 37.6176 + (random.random() - 0.5) * 0.01,
            'heading': random.random() * 360,
            'status': 'available',
            'lastUpdate': datetime.now().isoformat()
        })
    
    logger.info("Mock drivers initialized", count=len(mock_drivers))

def update_mock_drivers():
    """Обновление позиций водителей-заглушек"""
    global mock_drivers
    
    for driver in mock_drivers:
        # Легкий дрейф позиции
        driver['latitude'] += (random.random() - 0.5) * 0.0001
        driver['longitude'] += (random.random() - 0.5) * 0.0001
        driver['heading'] += (random.random() - 0.5) * 10
        driver['heading'] %= 360
        driver['lastUpdate'] = datetime.now().isoformat()
        
        # Случайно меняем статус
        if random.random() < 0.1:  # 10% вероятность
            driver['status'] = random.choice(['available', 'busy', 'offline'])

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("Starting Geo Service", env=ENV, port=PORT)
    
    # Инициализируем заглушку водителей
    init_mock_drivers()
    
    # Запускаем обновление водителей
    asyncio.create_task(driver_update_task())
    
    yield
    logger.info("Shutting down Geo Service")
    await http_client.aclose()

async def driver_update_task():
    """Задача обновления позиций водителей"""
    while True:
        try:
            update_mock_drivers()
            await asyncio.sleep(1)  # Обновляем каждую секунду
        except Exception as e:
            logger.error("Driver update task failed", error=str(e))
            await asyncio.sleep(5)

# Создание FastAPI приложения
app = FastAPI(
    title="MagaDrive Geo Service",
    description="Сервис геолокации и маршрутов",
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
        service="geo-service"
    )

# Ready check
@app.get("/readyz", response_model=HealthResponse)
async def ready_check():
    try:
        # Проверяем доступность MapTiler API
        if MAPTILER_API_KEY:
            test_url = f"https://api.maptiler.com/geocoding/55.7558,37.6176.json?key={MAPTILER_API_KEY}"
            response = await http_client.get(test_url)
            if response.status_code == 200:
                return HealthResponse(
                    status="ready",
                    timestamp=datetime.now().isoformat(),
                    service="geo-service"
                )
        
        # Если нет API ключа, все равно считаем готовым
        return HealthResponse(
            status="ready",
            timestamp=datetime.now().isoformat(),
            service="geo-service"
        )
        
    except Exception as e:
        logger.error("Service not ready", error=str(e))
        raise HTTPException(status_code=503, detail="Service not ready")

# Получение ETA и расстояния для маршрута
@app.post("/route/eta", response_model=ApiResponse)
async def get_route_eta(request: RouteRequest, req: Request):
    try:
        trace_id = req.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        # Создаем ключ кэша
        cache_key = f"{request.origin}_{request.destination}"
        
        # Проверяем кэш
        if cache_key in route_cache:
            cached_data = route_cache[cache_key]
            if (datetime.now().timestamp() - cached_data['timestamp']) < CACHE_TTL_SEC:
                logger.info("Route served from cache", origin=request.origin, destination=request.destination)
                return ApiResponse(
                    data=cached_data['data'],
                    traceId=trace_id
                )
        
        # Если нет API ключа MapTiler, используем заглушку
        if not MAPTILER_API_KEY:
            # Простая заглушка для Москвы
            if "красная площадь" in request.origin.lower() and "тверская" in request.destination.lower():
                route_data = {
                    'etaSeconds': 300,  # 5 минут
                    'distanceMeters': 2500.0
                }
            else:
                route_data = {
                    'etaSeconds': 600,  # 10 минут
                    'distanceMeters': 5000.0
                }
        else:
            # Реальный запрос к MapTiler
            try:
                # Геокодируем адреса
                origin_coords = await geocode_address(request.origin)
                dest_coords = await geocode_address(request.destination)
                
                if not origin_coords or not dest_coords:
                    raise HTTPException(status_code=400, detail="Failed to geocode addresses")
                
                # Получаем маршрут
                route_data = await get_maptiler_route(origin_coords, dest_coords)
                
            except Exception as e:
                logger.error("MapTiler API failed, using fallback", error=str(e))
                # Fallback на заглушку
                route_data = {
                    'etaSeconds': 600,
                    'distanceMeters': 5000.0
                }
        
        # Сохраняем в кэш
        route_cache[cache_key] = {
            'data': route_data,
            'timestamp': datetime.now().timestamp()
        }
        
        # Очищаем старые записи кэша
        cleanup_cache()
        
        return ApiResponse(
            data=route_data,
            traceId=trace_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get route ETA", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Получение списка водителей в bounding box
@app.get("/drivers", response_model=ApiResponse)
async def get_drivers(bbox: str, req: Request):
    try:
        trace_id = req.headers.get("X-Request-Id") or str(uuid.uuid4())
        
        # Парсим bbox (west,south,east,north)
        try:
            west, south, east, north = map(float, bbox.split(','))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid bbox format")
        
        # Фильтруем водителей по bounding box
        drivers_in_bbox = []
        for driver in mock_drivers:
            if (west <= driver['longitude'] <= east and 
                south <= driver['latitude'] <= north):
                drivers_in_bbox.append(driver)
        
        logger.info("Drivers in bbox", bbox=bbox, count=len(drivers_in_bbox))
        
        return ApiResponse(
            data={'drivers': drivers_in_bbox},
            traceId=trace_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get drivers", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

async def geocode_address(address: str) -> Optional[Dict[str, float]]:
    """Геокодирование адреса через MapTiler"""
    try:
        url = f"https://api.maptiler.com/geocoding/{address}.json"
        params = {
            'key': MAPTILER_API_KEY,
            'country': 'RU',
            'language': 'ru'
        }
        
        response = await http_client.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('features'):
                coords = data['features'][0]['geometry']['coordinates']
                return {
                    'longitude': coords[0],
                    'latitude': coords[1]
                }
        
        return None
        
    except Exception as e:
        logger.error("Geocoding failed", address=address, error=str(e))
        return None

async def get_maptiler_route(origin: Dict[str, float], destination: Dict[str, float]) -> Dict[str, Any]:
    """Получение маршрута через MapTiler Directions API"""
    try:
        url = "https://api.maptiler.com/directions/v2/route"
        params = {
            'key': MAPTILER_API_KEY,
            'start': f"{origin['longitude']},{origin['latitude']}",
            'end': f"{destination['longitude']},{destination['latitude']}",
            'profile': 'driving',
            'units': 'metric'
        }
        
        response = await http_client.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('routes'):
                route = data['routes'][0]
                return {
                    'etaSeconds': int(route['duration']),
                    'distanceMeters': route['distance']
                }
        
        # Fallback
        return {
            'etaSeconds': 600,
            'distanceMeters': 5000.0
        }
        
    except Exception as e:
        logger.error("MapTiler routing failed", error=str(e))
        return {
            'etaSeconds': 600,
            'distanceMeters': 5000.0
        }

def cleanup_cache():
    """Очистка устаревших записей кэша"""
    global route_cache
    
    current_time = datetime.now().timestamp()
    expired_keys = [
        key for key, value in route_cache.items()
        if (current_time - value['timestamp']) > CACHE_TTL_SEC
    ]
    
    for key in expired_keys:
        del route_cache[key]
    
    if expired_keys:
        logger.info("Cache cleaned", expired_count=len(expired_keys))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
