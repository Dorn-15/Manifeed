import os
from typing import List, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.health_router import health_router


def _parse_cors_origins() -> Tuple[List[str], bool]:
    raw_origins = os.getenv("CORS_ORIGINS", "")
    if raw_origins.strip() == "*":
        return ["*"], False

    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    if origins:
        return origins, True
    return ["http://localhost:3000", "http://localhost:3001"], True


def create_app() -> FastAPI:
    app = FastAPI(title="Manifeed API")

    cors_origins, allow_credentials = _parse_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)

    return app


app = create_app()
