from fastapi import APIRouter

from app.incidents.router import exports_router, router as incidents_router
from app.partners.router import router as partners_router
from app.reviews.router import router as analyst_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(incidents_router)
api_router.include_router(exports_router)
api_router.include_router(analyst_router)
api_router.include_router(partners_router)
