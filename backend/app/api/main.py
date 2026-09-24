from fastapi import APIRouter

from app.api.routes import items, login, private, users, utils
from app.core.config import settings
from app.fleet.router import router as fleet_router
from app.fuel.router import router as fuel_router
from app.fuel_optimization.router import router as fuel_optimization_router
from app.geocoding.router import router as geocoding_router
from app.map.router import router as map_router
from app.routing.router import router as routing_router

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(fleet_router)
api_router.include_router(fuel_router)
api_router.include_router(fuel_optimization_router)
api_router.include_router(geocoding_router)
api_router.include_router(routing_router)
api_router.include_router(map_router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
