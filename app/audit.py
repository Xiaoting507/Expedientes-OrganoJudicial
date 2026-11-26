"""PB-03: auditoría y trazabilidad con cadena de hashes (a prueba de manipulación).

Sprint 7 — integridad de la bitácora:
- SEC-09: los registros nuevos (versión 2) incluyen `expediente_id` e `ip` en el hash.
  Los registros anteriores (versión 1) se siguen verificando con la fórmula original,
  así la cadena existente no se rompe.
- SEC-10: la versión 2 usa HMAC-SHA256 con AUDIT_KEY, que vive fuera de la base de datos.
  Quien solo tenga acceso a la BD ya no puede recalcular la cadena completa.
- SEC-11: la lectura del último registro y la escritura del nuevo se serializan
  (cerrojo del proceso + pg_advisory_xact_lock en PostgreSQL), así dos peticiones
  simultáneas no generan dos registros con el mismo hash_anterior.

Sprint 9 — SEC-12: los eventos anónimos (consulta ciudadana y login con usuario inexistente)
ya no entran en la cadena: van a `registrar_acceso`, sin hash y con rotación por antigüedad.
`verificar_cadena` recorre la tabla por lotes (yield_per), sin cargarla entera en memoria.
"""
import hashlib
import hmac
import json
import threading
from datetime import timedelta, timezone

from fastapi import Request
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from .config import AUDIT_KEY
from .models import Auditoria, EventoAcceso

GENESIS = "0" * 64
VERSION_ACTUAL = 2
_CANDADO_PG = 7_420_260  # id del advisory lock de la bitácora

_cerrojo = threading.Lock()


def _contenido_v1(reg: Auditoria) -> str:
    return "|".join([reg.hash_anterior, reg.fecha.isoformat(), reg.usuario, reg.accion, reg.entidad,
                     reg.entidad_id, reg.antes, reg.despues])


def _calcular_hash(reg: Auditoria) -> str:
    if (reg.version or 1) == 1:
        return hashlib.sha256(_contenido_v1(reg).encode()).hexdigest()
    contenido = "|".join([_contenido_v1(reg), str(reg.expediente_id or ""), reg.ip or "", "v2"])
    return hmac.new(AUDIT_KEY.encode(), contenido.encode(), hashlib.sha256).hexdigest()


def _tomar_cerrojo(db: Session) -> None:
    """SEC-11: un solo escritor de la bitácora a la vez, hasta que termine la transacción."""
    if db.info.get("bitacora_bloqueada"):
        return
    _cerrojo.acquire()
    db.info["bitacora_bloqueada"] = True
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CANDADO_PG})


@event.listens_for(Session, "after_transaction_end")
def _soltar_cerrojo(session: Session, transaccion) -> None:
    if transaccion.parent is None and session.info.pop("bitacora_bloqueada", False):
        _cerrojo.release()


def registrar(
    db: Session,
    *,
    usuario: str,
    accion: str,
    entidad: str,
    entidad_id: str | int,
    antes: dict | None = None,
    despues: dict | None = None,
    expediente_id: int | None = None,
    request: Request | None = None,
) -> Auditoria:
    """Agrega un registro a la bitácora. Se llama dentro de la misma transacción del cambio."""
    from .models import ahora

    _tomar_cerrojo(db)
    ultimo = db.query(Auditoria).order_by(Auditoria.id.desc()).first()
    reg = Auditoria(
        fecha=ahora().replace(microsecond=0),
        usuario=usuario[:60],
        accion=accion,
        entidad=entidad,
        entidad_id=str(entidad_id),
        expediente_id=expediente_id,
        antes=json.dumps(antes or {}, ensure_ascii=False, default=str, sort_keys=True),
        despues=json.dumps(despues or {}, ensure_ascii=False, default=str, sort_keys=True),
        ip=(request.client.host if request and request.client else ""),
        hash_anterior=ultimo.hash if ultimo else GENESIS,
        version=VERSION_ACTUAL,
    )
    reg.hash = _calcular_hash(reg)
    db.add(reg)
    db.flush()  # el siguiente registro de la misma transacción debe ver este como "último"
    return reg


def registrar_acceso(db: Session, *, accion: str, usuario: str, referencia: str | int = "",
                     request: Request | None = None) -> EventoAcceso:
    """SEC-12: evento anónimo fuera de la cadena. Borra en la misma transacción lo que pasó la retención."""
    from .config import EVENTOS_RETENCION_DIAS
    from .models import ahora

    limite = ahora() - timedelta(days=EVENTOS_RETENCION_DIAS)
    db.query(EventoAcceso).filter(EventoAcceso.fecha < limite).delete(synchronize_session=False)
    ev = EventoAcceso(fecha=ahora().replace(microsecond=0), accion=accion, usuario=usuario[:60],
                      referencia=str(referencia)[:40], ip=(request.client.host if request and request.client else ""))
    db.add(ev)
    return ev


def verificar_cadena(db: Session) -> dict:
    """Recalcula la cadena. Además (SEC-09) cruza entidad_id con expediente_id en los registros de expedientes."""
    anterior = GENESIS
    total = 0
    v2 = 0
    for reg in db.query(Auditoria).order_by(Auditoria.id).yield_per(500):
        total += 1
        if reg.fecha.tzinfo is None:  # SQLite devuelve fechas sin zona; normalizamos para recalcular igual
            reg.fecha = reg.fecha.replace(tzinfo=timezone.utc)
        incoherente = (reg.version or 1) >= 2 and reg.entidad == "expediente" and reg.entidad_id.isdigit() \
            and reg.expediente_id is not None and int(reg.entidad_id) != reg.expediente_id
        if reg.hash_anterior != anterior or _calcular_hash(reg) != reg.hash or incoherente:
            db.expire(reg)
            return {"integra": False, "registros": total, "roto_en_id": reg.id, "registros_v2": v2}
        v2 += (reg.version or 1) >= 2
        db.expire(reg)
        anterior = reg.hash
    return {"integra": True, "registros": total, "roto_en_id": None, "registros_v2": v2}
