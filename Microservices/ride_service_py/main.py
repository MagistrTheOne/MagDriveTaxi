#!/usr/bin/env python3
"""
MagaDrive Ride Service
Управление поездками, статусами, идемпотентность
"""

import os
import uuid
import time
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from sqlalchemy.sql import text

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
    origin: Dict[str, float]  # {"lat": 55.7558, "lng": 37.6176}
    dest: Dict[str, float]    # {"lat": 55.7517, "lng": 37.6178}
    class_type: str            # "comfort", "business", "xl"

class RideResponse(BaseModel):
    rideId: str
    status: str
    etaSec: Optional[int] = None
    price: Optional[int] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str

# Конфигурация
ENV = os.getenv("ENV", "dev")
PORT = int(os.getenv("PORT", "7031"))
DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///data/ride.db")

# SQLAlchemy setup
Base = declarative_base()

class Ride(Base):
    __tablename__ = "rides"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    driver_id = Column(String, nullable=True)
    origin = Column(JSON, nullable=False)
    dest = Column(JSON, nullable=False)
    class_type = Column(String, nullable=False)
    price = Column(Integer, nullable=True)
    currency = Column(String, default="RUB")
    status = Column(String, default="requested")
    eta_sec = Column(Integer, nullable=True)
    distance_m = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, default=text("CURRENT_TIMESTAMP"))

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    
    key = Column(String, primary_key=True)
    ride_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=text("CURRENT_TIMESTAMP"))

# Database engine
engine = None
AsyncSessionLocal = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global engine, AsyncSessionLocal
    
    logger.info("Starting Ride Service", env=ENV, port=PORT)
    
    # Создаем engine и сессии
    engine = create_async_engine(DB_URL, echo=ENV == "dev")
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Создаем таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database initialized")
    yield
    
    logger.info("Shutting down Ride Service")
    if engine:
        await engine.dispose()

# Создание FastAPI приложения
app = FastAPI(
    title="MagaDrive Ride Service",
    description="Управление поездками и статусами",
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

# Dependency для получения сессии БД
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Health checks
@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Liveness probe"""
    return HealthResponse(
        status="healthy",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        service="ride-service"
    )

@app.get("/readyz", response_model=HealthResponse)
async def readiness_check():
    """Readiness probe"""
    try:
        # Проверяем подключение к БД
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        
        return HealthResponse(
            status="ready",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            service="ride-service"
        )
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Database not ready")

# API роуты
@app.post("/rides", response_model=RideResponse)
async def create_ride(request: CreateRideRequest, db: AsyncSession = Depends(get_db)):
    """Создание новой поездки"""
    try:
        # Проверяем идемпотентность
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            raise HTTPException(status_code=400, detail="Idempotency-Key header required")
        
        # Проверяем, не использовался ли уже этот ключ
        existing_key = await db.execute(
            text("SELECT ride_id FROM idempotency_keys WHERE key = :key"),
            {"key": idempotency_key}
        )
        existing_result = existing_key.fetchone()
        
        if existing_result:
            # Возвращаем существующую поездку
            ride_id = existing_result[0]
            ride = await db.execute(
                text("SELECT * FROM rides WHERE id = :ride_id"),
                {"ride_id": ride_id}
            )
            ride_data = ride.fetchone()
            
            return RideResponse(
                rideId=ride_data[0],
                status=ride_data[8],  # status
                etaSec=ride_data[9],  # eta_sec
                price=ride_data[6]    # price
            )
        
        # Создаем новую поездку
        ride_id = str(uuid.uuid4())
        
        # Простой расчет цены (позже заменим на pricing service)
        base_price = {"comfort": 1000, "business": 2000, "xl": 3000}
        price = base_price.get(request.class_type, 1000)
        
        # Простой расчет ETA (позже заменим на geo service)
        # Haversine формула для примерного расчета
        import math
        lat1, lng1 = request.origin["lat"], request.origin["lng"]
        lat2, lng2 = request.dest["lat"], request.dest["lng"]
        
        R = 6371000  # радиус Земли в метрах
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lng/2) * math.sin(delta_lng/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance_m = int(R * c)
        
        # Примерное время в пути (средняя скорость 15 м/с)
        eta_sec = int(distance_m / 15)
        
        # Сохраняем поездку
        await db.execute(
            text("""
                INSERT INTO rides (id, user_id, origin, dest, class_type, price, 
                                 currency, status, eta_sec, distance_m)
                VALUES (:id, :user_id, :origin, :dest, :class_type, :price,
                       :currency, :status, :eta_sec, :distance_m)
            """),
            {
                "id": ride_id,
                "user_id": str(uuid.uuid4()),  # Временно генерируем
                "origin": request.origin,
                "dest": request.dest,
                "class_type": request.class_type,
                "price": price,
                "currency": "RUB",
                "status": "requested",
                "eta_sec": eta_sec,
                "distance_m": distance_m
            }
        )
        
        # Сохраняем ключ идемпотентности
        await db.execute(
            text("INSERT INTO idempotency_keys (key, ride_id) VALUES (:key, :ride_id)"),
            {"key": idempotency_key, "ride_id": ride_id}
        )
        
        await db.commit()
        
        logger.info("Ride created", ride_id=ride_id, class_type=request.class_type)
        
        return RideResponse(
            rideId=ride_id,
            status="requested",
            etaSec=eta_sec,
            price=price
        )
        
    except Exception as e:
        await db.rollback()
        logger.error("Create ride failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/rides/{ride_id}")
async def get_ride(ride_id: str, db: AsyncSession = Depends(get_db)):
    """Получение информации о поездке"""
    try:
        result = await db.execute(
            text("SELECT * FROM rides WHERE id = :ride_id"),
            {"ride_id": ride_id}
        )
        ride_data = result.fetchone()
        
        if not ride_data:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        # Преобразуем в словарь
        ride = {
            "id": ride_data[0],
            "userId": ride_data[1],
            "driverId": ride_data[2],
            "origin": ride_data[3],
            "dest": ride_data[4],
            "class": ride_data[5],
            "price": ride_data[6],
            "currency": ride_data[7],
            "status": ride_data[8],
            "etaSec": ride_data[9],
            "distanceM": ride_data[10],
            "createdAt": ride_data[11].isoformat() if ride_data[11] else None,
            "updatedAt": ride_data[12].isoformat() if ride_data[12] else None
        }
        
        return ride
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get ride failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/rides/{ride_id}/cancel")
async def cancel_ride(ride_id: str, db: AsyncSession = Depends(get_db)):
    """Отмена поездки"""
    try:
        # Проверяем существование поездки
        result = await db.execute(
            text("SELECT status FROM rides WHERE id = :ride_id"),
            {"ride_id": ride_id}
        )
        ride_data = result.fetchone()
        
        if not ride_data:
            raise HTTPException(status_code=404, detail="Ride not found")
        
        current_status = ride_data[0]
        if current_status in ["completed", "canceled"]:
            raise HTTPException(status_code=400, detail="Cannot cancel completed or canceled ride")
        
        # Отменяем поездку
        await db.execute(
            text("UPDATE rides SET status = 'canceled', updated_at = CURRENT_TIMESTAMP WHERE id = :ride_id"),
            {"ride_id": ride_id}
        )
        
        await db.commit()
        
        logger.info("Ride canceled", ride_id=ride_id)
        
        return {"status": "canceled"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Cancel ride failed", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=ENV == "dev"
    )
