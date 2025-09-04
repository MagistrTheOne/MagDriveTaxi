#!/usr/bin/env python3
"""
MagaDrive Geo Service - T8-T10
Прокси MapTiler Directions и заглушка водителей
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import random
import math

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
MAPTILER_API_KEY = os.getenv('MAPTILER_API_KEY', 'SjhYKAeXJxWy3pPcQc2G')
MAPTILER_BASE_URL = 'https://api.maptiler.com/directions/driving'
CACHE_TTL = int(os.getenv('CACHE_TTL', '600'))  # 10 минут

# HTTP клиент
http_client = httpx.AsyncClient(timeout=10.0)

# Кэш для ETA запросов
route_cache: Dict[str, Dict[str, Any]] = {}

# Заглушка водителей в памяти
fake_drivers = []

app = FastAPI(
    title="MagaDrive Geo Service",
    description="Сервис геолокации и маршрутизации T8-T10",
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
class RouteEtaRequest(BaseModel):
    originLat: float
    originLng: float
    destLat: float
    destLng: float

class DriversRequest(BaseModel):
    lat: float
    lng: float
    radius: Optional[float] = 5000

class Driver(BaseModel):
    id: str
    name: str
    phone: str
    rating: float
    vehicleClass: str
    vehicleNumber: str
    lat: float
    lng: float
    heading: Optional[float] = None
    speed: Optional[float] = None
    eta: Optional[int] = None
    distance: Optional[float] = None

# Инициализация заглушки водителей
def init_fake_drivers():
    """Инициализация заглушки водителей в памяти"""
    global fake_drivers
    
    # Генерируем 20-30 водителей вокруг Москвы
    moscow_center_lat = 55.7558
    moscow_center_lng = 37.6176
    
    names = ['Алексей', 'Дмитрий', 'Сергей', 'Андрей', 'Михаил', 'Владимир', 'Александр', 'Николай']
    vehicle_classes = ['economy', 'comfort', 'business']
    
    for i in range(25):
        # Случайное расположение в радиусе 10 км от центра
        angle = random.uniform(0, 2 * math.pi)
        radius_km = random.uniform(1, 10)
        
        # Преобразуем км в градусы (примерно)
        lat_offset = (radius_km / 111.0) * math.cos(angle)
        lng_offset = (radius_km / (111.0 * math.cos(math.radians(moscow_center_lat)))) * math.sin(angle)
        
        driver = {
            "id": f"driver_{i+1000}",
            "name": f"{random.choice(names)} {chr(65 + i)}.",
            "phone": f"+7 (999) {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}",
            "rating": round(random.uniform(4.0, 5.0), 1),
            "vehicleClass": random.choice(vehicle_classes),
            "vehicleNumber": f"{random.choice(['А', 'В', 'Е', 'К', 'М'])}{random.randint(100, 999)}{random.choice(['АА', 'ВВ', 'ЕЕ'])}77",
            "lat": moscow_center_lat + lat_offset,
            "lng": moscow_center_lng + lng_offset,
            "heading": random.uniform(0, 360),
            "speed": random.uniform(0, 60),  # км/ч
            "lastUpdate": datetime.utcnow()
        }
        
        fake_drivers.append(driver)
    
    logger.info(f"Initialized {len(fake_drivers)} fake drivers")

# Инициализация при старте
init_fake_drivers()

# Фоновая задача для обновления позиций водителей
async def update_drivers_positions():
    """Фоновое обновление позиций водителей каждую секунду"""
    while True:
        try:
            for driver in fake_drivers:
                # Небольшое случайное движение
                lat_delta = random.uniform(-0.0005, 0.0005)  # ~50 метров
                lng_delta = random.uniform(-0.0005, 0.0005)
                
                driver["lat"] += lat_delta
                driver["lng"] += lng_delta
                driver["heading"] = (driver["heading"] + random.uniform(-10, 10)) % 360
                driver["speed"] = max(0, min(80, driver["speed"] + random.uniform(-5, 5)))
                driver["lastUpdate"] = datetime.utcnow()
            
            await asyncio.sleep(1)  # Обновляем каждую секунду
            
        except Exception as e:
            logger.error(f"Failed to update drivers positions: {e}")
            await asyncio.sleep(5)

# Запускаем фоновую задачу
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(update_drivers_positions())

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
        # Проверяем доступность MapTiler API
        moscow_center_lat = 55.7558
        moscow_center_lng = 37.6176
        
        test_response = await http_client.get(
            f"{MAPTILER_BASE_URL}/{moscow_center_lng},{moscow_center_lat};{moscow_center_lng+0.01},{moscow_center_lat+0.01}",
            params={"key": MAPTILER_API_KEY},
            timeout=5.0
        )
        
        maptiler_available = test_response.status_code == 200
        
        return {
            "status": "ready" if maptiler_available else "degraded",
            "maptiler": "available" if maptiler_available else "unavailable",
            "drivers": len(fake_drivers)
        }
    except Exception as e:
        logger.error(f"Ready check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)}
        )

# Функция для создания ключа кэша
def get_cache_key(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> str:
    """Создание ключа кэша для маршрута"""
    return f"{origin_lat:.6f},{origin_lng:.6f}_{dest_lat:.6f},{dest_lng:.6f}"

# Функция для проверки актуальности кэша
def is_cache_valid(cache_entry: Dict[str, Any]) -> bool:
    """Проверка актуальности записи в кэше"""
    cached_time = datetime.fromisoformat(cache_entry["timestamp"])
    return (datetime.utcnow() - cached_time).total_seconds() < CACHE_TTL

@app.post("/route/eta")
async def get_route_eta(request: RouteEtaRequest, http_request: Request):
    """Прокси MapTiler Directions для получения ETA и расстояния"""
    trace_id = http_request.state.trace_id
    
    try:
        # Проверяем кэш
        cache_key = get_cache_key(request.originLat, request.originLng, request.destLat, request.destLng)
        
        if cache_key in route_cache and is_cache_valid(route_cache[cache_key]):
            cached_data = route_cache[cache_key]
            logger.info(f"Route ETA from cache: {cache_key}", extra={'traceId': trace_id})
            
            return {
                "data": {
                    "etaSec": cached_data["etaSec"],
                    "distanceM": cached_data["distanceM"]
                },
                "error": None,
                "traceId": trace_id
            }
        
        # Запрос к MapTiler API
        coordinates = f"{request.originLng},{request.originLat};{request.destLng},{request.destLat}"
        
        response = await http_client.get(
            f"{MAPTILER_BASE_URL}/{coordinates}",
            params={
                "key": MAPTILER_API_KEY,
                "overview": "false",
                "steps": "false"
            },
            timeout=8.0
        )
        
        if response.status_code == 200:
            maptiler_data = response.json()
            
            if maptiler_data.get("routes"):
                route = maptiler_data["routes"][0]
                distance_m = route["distance"]  # в метрах
                duration_s = route["duration"]  # в секундах
                
                # Сохраняем в кэш
                cache_data = {
                    "etaSec": int(duration_s),
                    "distanceM": distance_m,
                    "timestamp": datetime.utcnow().isoformat()
                }
                route_cache[cache_key] = cache_data
                
                logger.info(f"Route ETA calculated: {distance_m}m, {duration_s}s", extra={'traceId': trace_id})
                
                return {
                    "data": {
                        "etaSec": int(duration_s),
                        "distanceM": distance_m
                    },
                    "error": None,
                    "traceId": trace_id
                }
            else:
                # Fallback к расчету по прямой
                return _calculate_direct_route(request, trace_id)
        else:
            # Fallback к расчету по прямой
            logger.warning(f"MapTiler API error: {response.status_code}", extra={'traceId': trace_id})
            return _calculate_direct_route(request, trace_id)
            
    except Exception as e:
        logger.error(f"Route ETA calculation failed: {e}", extra={'traceId': trace_id})
        # Fallback к расчету по прямой
        return _calculate_direct_route(request, trace_id)

def _calculate_direct_route(request: RouteEtaRequest, trace_id: str) -> Dict[str, Any]:
    """Fallback расчет маршрута по прямой линии"""
    try:
        # Расчет расстояния по формуле гаверсинуса
        lat1, lng1 = math.radians(request.originLat), math.radians(request.originLng)
        lat2, lng2 = math.radians(request.destLat), math.radians(request.destLng)
        
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        distance_km = 6371 * c  # Радиус Земли в км
        distance_m = distance_km * 1000
        
        # Примерная скорость в городе 30 км/ч
        duration_s = int((distance_km / 30) * 3600)
        
        logger.info(f"Direct route calculated: {distance_m}m, {duration_s}s", extra={'traceId': trace_id})
        
        return {
            "data": {
                "etaSec": duration_s,
                "distanceM": distance_m
            },
            "error": None,
            "traceId": trace_id
        }
        
    except Exception as e:
        logger.error(f"Direct route calculation failed: {e}", extra={'traceId': trace_id})
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "error": {"code": "ROUTE_CALCULATION_FAILED", "message": str(e)},
                "traceId": trace_id
            }
        )

@app.get("/drivers")
async def get_available_drivers(
    lat: float,
    lng: float,
    radius: float = 5000,
    http_request: Request = None
):
    """Получение доступных водителей в радиусе (заглушка)"""
    trace_id = getattr(http_request.state, 'trace_id', str(uuid.uuid4())) if http_request else str(uuid.uuid4())
    
    try:
        # Фильтруем водителей по радиусу
        nearby_drivers = []
        
        for driver in fake_drivers:
            # Расчет расстояния в метрах
            distance = _calculate_distance(lat, lng, driver["lat"], driver["lng"])
            
            if distance <= radius:
                # Добавляем расстояние и ETA
                eta_minutes = max(1, int(distance / 500))  # ~30 км/ч средняя скорость
                
                driver_info = {
                    "id": driver["id"],
                    "name": driver["name"],
                    "phone": driver["phone"],
                    "rating": driver["rating"],
                    "vehicleClass": driver["vehicleClass"],
                    "vehicleNumber": driver["vehicleNumber"],
                    "lat": driver["lat"],
                    "lng": driver["lng"],
                    "heading": driver["heading"],
                    "speed": driver["speed"],
                    "distance": round(distance, 1),
                    "eta": eta_minutes * 60,  # в секундах
                    "lastUpdate": driver["lastUpdate"].isoformat()
                }
                
                nearby_drivers.append(driver_info)
        
        # Сортируем по расстоянию
        nearby_drivers.sort(key=lambda d: d["distance"])
        
        # Ограничиваем до 10 ближайших
        nearby_drivers = nearby_drivers[:10]
        
        logger.info(f"Found {len(nearby_drivers)} drivers within {radius}m", extra={'traceId': trace_id})
        
        return {
            "data": nearby_drivers,
            "error": None,
            "traceId": trace_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get available drivers: {e}", extra={'traceId': trace_id})
        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "error": {"code": "DRIVERS_FETCH_FAILED", "message": str(e)},
                "traceId": trace_id
            }
        )

def _calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Расчет расстояния между двумя точками в метрах"""
    # Формула гаверсинуса
    lat1_rad = math.radians(lat1)
    lng1_rad = math.radians(lng1)
    lat2_rad = math.radians(lat2)
    lng2_rad = math.radians(lng2)
    
    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return 6371000 * c  # Радиус Земли в метрах

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )
