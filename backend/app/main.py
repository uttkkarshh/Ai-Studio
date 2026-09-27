from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text

from app.api.findings import router as findings_router
from app.api.projects import router as projects_router
from app.api.parts import history_router, router as parts_router
from app.api.scripts import router as scripts_router
from app.api.sources import router as sources_router
from app.db.database import engine


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/health/db")
def database_health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}