#!/usr/bin/env python3
"""
MagaDrive Geo Service
MapTiler интеграция, гео-расчеты, кэш водителей
"""

import os
import uuid
import time
import math
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aioredis
import json

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
class RouteRequest(BaseModel):
    origin: Dict[str, float]  # {"lat": 55.7558, "lng": 37.6176}
    dest: Dict[str, float]    # {"lat": 55.7517, "lng": 37.6178}

class RouteResponse(BaseModel):
    etaSec: int
    distanceM: int
    route: Optional[List[Dict[str, float]]] = None

class DriverLocation(BaseModel):
    driverId: str
    lat: float
    lng: float
    heading: Optional[float] = None
    speed: Optional[float] = None
    updatedAt: str

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str

# Конфигурация
ENV = os.getenv("ENV", "dev")
PORT = int(os.getenv("PORT", "7032"))
MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY", "SjhYKAeXJxWy3pPcQc2G")
CACHE_TTL_SEC = int(os.getenv("CACHE_TTL_SEC", "600"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Redis клиент
redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global redis_client
    
    logger.info("Starting Geo Service", env=ENV, port=PORT)
    
    # Подключаемся к Redis
    try:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning("Redis not available, using in-memory cache", error=str(e))
        redis_client = None
    
    yield
    
    logger.info("Shutting down Geo Service")
    if redis_client:
        await redis_client.close()

# Создание FastAPI приложения
app = FastAPI(
    title="MagaDrive Geo Service",
    description="Гео-сервис с MapTiler интеграцией",
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

# Утилиты для гео-расчетов
def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Расчет расстояния между двумя точками по формуле Haversine"""
    R = 6371000  # радиус Земли в метрах
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lng/2) * math.sin(delta_lng/2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def calculate_eta(distance_m: float, avg_speed_mps: float = 15.0) -> int:
    """Расчет времени в пути"""
    return int(distance_m / avg_speed_mps)

# Кэш для водителей (если Redis недоступен)
drivers_cache = {}

async def get_cached_drivers(bbox: str) -> Optional[List[DriverLocation]]:
    """Получение водителей из кэша"""
    if redis_client:
        try:
            cached = await redis_client.get(f"drivers:{bbox}")
            if cached:
                data = json.loads(cached)
                return [DriverLocation(**driver) for driver in data]
        except Exception as e:
            logger.warning("Redis cache error", error=str(e))
    
    # Fallback к in-memory кэшу
    return drivers_cache.get(bbox)

async def set_cached_drivers(bbox: str, drivers: List[DriverLocation]):
    """Сохранение водителей в кэш"""
    if redis_client:
        try:
            data = [driver.dict() for driver in drivers]
            await redis_client.setex(f"drivers:{bbox}", CACHE_TTL_SEC, json.dumps(data))
        except Exception as e:
            logger.warning("Redis cache error", error=str(e))
    
    # Fallback к in-memory кэшу
    drivers_cache[bbox] = drivers

# Health checks
@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Liveness probe"""
    return HealthResponse(
        status="healthy",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        service="geo-service"
    )

@app.get("/readyz", response_model=HealthResponse)
async def readiness_check():
    """Readiness probe"""
    try:
        # Проверяем Redis если доступен
        if redis_client:
            await redis_client.ping()
        
        return HealthResponse(
            status="ready",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            service="geo-service"
        )
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service not ready")

# API роуты
@app.get("/drivers")
async def get_drivers(bbox: str):
    """Поиск водителей в bounding box"""
    try:
        # Парсим bbox: "lat1,lng1,lat2,lng2"
        try:
            lat1, lng1, lat2, lng2 = map(float, bbox.split(','))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid bbox format. Use: lat1,lng1,lat2,lng2")
        
        # Проверяем кэш
        cached_drivers = await get_cached_drivers(bbox)
        if cached_drivers:
            logger.info("Drivers returned from cache", bbox=bbox, count=len(cached_drivers))
            return cached_drivers
        
        # Генерируем тестовых водителей (в реальном приложении - запрос к БД)
        test_drivers = []
        for i in range(5):
            # Случайная позиция в bounding box
            lat = lat1 + (lat2 - lat1) * (0.3 + 0.4 * (i / 4))
            lng = lng1 + (lng2 - lng1) * (0.3 + 0.4 * (i / 4))
            
            driver = DriverLocation(
                driverId=f"driver_{i+1}",
                lat=lat,
                lng=lng,
                heading=90 + i * 45,  # Случайное направление
                speed=10 + i * 2,     # Случайная скорость
                updatedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )
            test_drivers.append(driver)
        
        # Кэшируем результат
        await set_cached_drivers(bbox, test_drivers)
        
        logger.info("Drivers generated and cached", bbox=bbox, count=len(test_drivers))
        return test_drivers
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get drivers failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/route/eta", response_model=RouteResponse)
async def calculate_route_eta(request: RouteRequest):
    """Расчет маршрута и ETA через MapTiler"""
    try:
        # Сначала пробуем простой расчет по Haversine
        distance_m = haversine_distance(
            request.origin["lat"], request.origin["lng"],
            request.dest["lat"], request.dest["lng"]
        )
        
        # Базовый ETA
        eta_sec = calculate_eta(distance_m)
        
        # Если есть MapTiler API ключ, пробуем получить реальный маршрут
        route_points = None
        if MAPTILER_API_KEY and MAPTILER_API_KEY != "<MAPTILER_KEY>":
            try:
                # Формируем URL для MapTiler Directions API
                origin_str = f"{request.origin['lng']},{request.origin['lat']}"
                dest_str = f"{request.dest['lng']},{request.dest['lat']}"
                
                url = f"https://api.maptiler.com/directions/v2/route"
                params = {
                    "key": MAPTILER_API_KEY,
                    "origin": origin_str,
                    "destination": dest_str,
                    "profile": "driving",
                    "geometries": "geojson"
                }
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("routes") and len(data["routes"]) > 0:
                            route = data["routes"][0]
                            
                            # Обновляем расстояние и время
                            distance_m = int(route.get("distance", distance_m))
                            eta_sec = int(route.get("duration", eta_sec))
                            
                            # Извлекаем точки маршрута
                            if route.get("geometry", {}).get("coordinates"):
                                coords = route["geometry"]["coordinates"]
                                route_points = [
                                    {"lng": coord[0], "lat": coord[1]} 
                                    for coord in coords
                                ]
                            
                            logger.info("Route calculated via MapTiler", 
                                      distance_m=distance_m, eta_sec=eta_sec)
                        else:
                            logger.warning("No routes found in MapTiler response")
                    else:
                        logger.warning("MapTiler API error", 
                                     status_code=response.status_code)
                        
            except Exception as e:
                logger.warning("MapTiler integration failed, using fallback", error=str(e))
        
        return RouteResponse(
            etaSec=eta_sec,
            distanceM=int(distance_m),
            route=route_points
        )
        
    except Exception as e:
        logger.error("Calculate route ETA failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/drivers/update")
async def update_driver_location(request: DriverLocation):
    """Обновление позиции водителя"""
    try:
        # В реальном приложении - сохранение в БД
        # Здесь просто логируем
        logger.info("Driver location updated", 
                   driver_id=request.driverId, 
                   lat=request.lat, 
                   lng=request.lng)
        
        return {"status": "updated"}
        
    except Exception as e:
        logger.error("Update driver location failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=ENV == "dev"
    )
