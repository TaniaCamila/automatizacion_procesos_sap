from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config.logger import LoggerManager
from .routes import (
    configuration,
    dashboard,
    history,
    home,
    img,
    reports,
    sen,
    system,
    treasury,
)


logger = LoggerManager.get_logger(__name__)

app = FastAPI(
    title="CBO Operations Analytics API",
    description=(
        "API de lectura sobre artefactos del pipeline Informe Margen. "
        "No recalcula FBL1N en los endpoints GET."
    ),
    version="0.1.0-int02",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    logger.info(
        "HTTP %s %s — inicio",
        request.method,
        request.url.path,
    )
    try:
        response = await call_next(request)
    except Exception:
        elapsed = time.perf_counter() - started
        logger.exception(
            "HTTP %s %s — error (%.2f s)",
            request.method,
            request.url.path,
            elapsed,
        )
        raise

    elapsed = time.perf_counter() - started
    logger.info(
        "HTTP %s %s — fin status=%s (%.2f s)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "code": "HTTP_ERROR",
            "message": "Error interno del servidor",
            "detail": str(exc),
        },
    )


app.include_router(system.router, prefix="/api")
app.include_router(configuration.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(home.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(treasury.router, prefix="/api")
app.include_router(sen.router, prefix="/api")
app.include_router(img.router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "CBO Operations Analytics API",
        "docs": "/docs",
        "api": "/api",
    }
