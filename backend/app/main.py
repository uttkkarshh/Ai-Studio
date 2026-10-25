import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sqlalchemy import text

from app.api.findings import router as findings_router
from app.api.projects import router as projects_router
from app.api.parts import history_router, router as parts_router
from app.api.scripts import router as scripts_router
from app.api.sources import router as sources_router
from app.core.logging_config import configure_logging
from app.core.request_context import request_id_context
from app.db.database import engine


configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(parts_router)
app.include_router(history_router)
app.include_router(scripts_router)
app.include_router(sources_router)
app.include_router(findings_router)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = str(uuid4())
    token = request_id_context.set(request_id)
    request.state.request_id = request_id
    started_at = perf_counter()
    logger.info(
        "http request started method=%s path=%s",
        request.method,
        request.url.path,
    )

    try:
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.exception(
                "Unhandled request failure method=%s path=%s request_id=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                request_id,
                duration_ms,
            )
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id},
            )

        response.headers["X-Request-ID"] = request_id
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        duration_ms = (perf_counter() - started_at) * 1000
        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            log_level,
            "http request completed method=%s route=%s status_code=%s duration_ms=%.2f",
            request.method,
            route_path,
            response.status_code,
            duration_ms,
        )
        return response
    finally:
        request_id_context.reset(token)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/health/db")
def database_health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}