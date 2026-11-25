"""Expediente Judicial Digital — MVP (Caso 1: Congestión Judicial)."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .config import APP_ENV, SEED_DEMO
from .db import Base, SessionLocal, engine
from .routers import admin, auth, congestion, documentos, expedientes, publico

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if APP_ENV == "produccion":
        # Sprint 7: en producción el esquema lo gobierna Alembic (migrations/); nunca create_all
        from .migraciones import actualizar_esquema

        actualizar_esquema()
    else:
        Base.metadata.create_all(engine)  # desarrollo, demo y pruebas
    if SEED_DEMO:
        from .seed import cargar

        from sqlalchemy.exc import IntegrityError

        with SessionLocal() as db:
            try:
                cargar(db)
            except IntegrityError:  # otra réplica ya cargó los datos demo
                db.rollback()
    yield


_DOCS = {} if APP_ENV != "produccion" else {"docs_url": None, "redoc_url": None, "openapi_url": None}  # SEC-16
app = FastAPI(title="Expediente Judicial Digital", version="0.7.0", lifespan=lifespan, **_DOCS)


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    """PB-04: cabeceras HTTP de seguridad (las revisa OpenVAS / cualquier escáner web)."""
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")  # SEC-17: datos del caso no se guardan en caché
    return resp  # SEC-18: la cabecera "server" se quita con uvicorn --no-server-header (Dockerfile)


app.include_router(auth.router)
app.include_router(documentos.router)
app.include_router(expedientes.router)
app.include_router(publico.router)
app.include_router(admin.router)
app.include_router(congestion.router)


@app.get("/healthz", tags=["ops"])
def healthz():
    """Liveness/readiness para Kubernetes."""
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory=STATIC), name="static")


# Interfaz React (frontend/ compilado en static/app). Si no hay build, se usa la interfaz HTML anterior.
SPA = STATIC / "app" / "index.html"


@app.get("/", include_in_schema=False)
@app.get("/expedientes", include_in_schema=False)
@app.get("/expedientes/{exp_id:int}", include_in_schema=False)
@app.get("/auditoria", include_in_schema=False)
@app.get("/congestion", include_in_schema=False)
def index(exp_id: int | None = None):
    return FileResponse(SPA if SPA.exists() else STATIC / "index.html")


@app.get("/consulta", include_in_schema=False)
def consulta_page():
    return FileResponse(SPA if SPA.exists() else STATIC / "consulta.html")
