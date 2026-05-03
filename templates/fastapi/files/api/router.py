from fastapi import APIRouter

from .routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)

# Add more routers here as your project grows:
# from .routes.auth import router as auth_router
# from .routes.users import router as users_router
# api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
# api_router.include_router(users_router, prefix="/users", tags=["users"])
