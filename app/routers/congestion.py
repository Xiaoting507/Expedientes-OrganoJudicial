"""HU-12 (Sprint 9): panel de congestión para el administrador.

Responde a la pregunta del caso: ¿dónde se atasca el proceso? Mide, sin exponer nombres de las partes:
  - expedientes activos y vencidos (plazo pasado sin sentencia ni archivo, igual que PB-06),
  - por estado: cuántos hay y cuántos días llevan en promedio en esa etapa,
  - por juez: carga activa, vencidos y antigüedad promedio,
  - los expedientes activos más antiguos.
Los días en la etapa se cuentan desde el último cambio de estado (actuación `cambio_estado`) o desde la radicación.
"""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Actuacion, EstadoExpediente, Expediente, Rol, Usuario
from ..security import requiere_rol

router = APIRouter(prefix="/api", tags=["congestión"])

CERRADOS = {EstadoExpediente.con_sentencia, EstadoExpediente.archivado}
ORDEN = list(EstadoExpediente)
TOP_ANTIGUOS = 5


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # SQLite devuelve fechas sin zona


def _dias(desde: datetime, ahora: datetime) -> float:
    return max(0.0, (ahora - _aware(desde)).total_seconds() / 86400)


def _promedio(valores: list[float]) -> float:
    return round(sum(valores) / len(valores), 1) if valores else 0.0


SIN_JUEZ = "Sin juez asignado"


def _nombre_juez(jueces: dict[int, str], jid: int | None) -> str:
    return jueces.get(jid, SIN_JUEZ) if jid else SIN_JUEZ


def _vencidos(expedientes: list[Expediente], hoy: date) -> set[int]:
    """Misma regla que las alertas de PB-06: plazo anterior a hoy y sin sentencia ni archivo."""
    return {e.id for e in expedientes
            if e.fecha_limite is not None and e.fecha_limite < hoy and e.estado not in CERRADOS}


def _por_estado(expedientes: list[Expediente], en_etapa: dict[int, float]) -> list[dict]:
    filas = []
    for est in ORDEN:
        grupo = [e for e in expedientes if e.estado == est]
        filas.append({"estado": est.value, "cantidad": len(grupo),
                      "dias_promedio_en_etapa": _promedio([en_etapa[e.id] for e in grupo])})
    return filas


def _por_juez(activos: list[Expediente], vencido: set[int], edad: dict[int, float],
              jueces: dict[int, str]) -> list[dict]:
    filas = []
    for jid in sorted({e.juez_id for e in activos}, key=lambda j: (j is None, j or 0)):
        grupo = [e for e in activos if e.juez_id == jid]
        filas.append({
            "juez_id": jid,
            "juez": _nombre_juez(jueces, jid),
            "activos": len(grupo),
            "vencidos": sum(e.id in vencido for e in grupo),
            "antiguedad_promedio_dias": _promedio([edad[e.id] for e in grupo]),
        })
    return sorted(filas, key=lambda j: (-j["vencidos"], -j["activos"]))


def _cuello_de_botella(por_estado: list[dict]) -> str | None:
    """La etapa activa (sin archivado) con más días promedio; None si no hay expedientes activos."""
    cuello = max(por_estado[:-1], key=lambda x: (x["dias_promedio_en_etapa"], x["cantidad"]))
    return cuello["estado"] if cuello["cantidad"] else None


def _mas_antiguos(activos: list[Expediente], edad: dict[int, float], en_etapa: dict[int, float],
                  vencido: set[int], jueces: dict[int, str]) -> list[dict]:
    antiguos = sorted(activos, key=lambda e: -edad[e.id])[:TOP_ANTIGUOS]
    return [{"id": e.id, "numero": e.numero, "estado": e.estado.value, "materia": e.materia,
             "juez": _nombre_juez(jueces, e.juez_id), "dias": round(edad[e.id], 1),
             "en_etapa_dias": round(en_etapa[e.id], 1), "vencido": e.id in vencido} for e in antiguos]


def calcular(expedientes: list[Expediente], ultimo_cambio: dict[int, datetime], jueces: dict[int, str],
             hoy: date, ahora: datetime) -> dict:
    """Función pura: recibe los datos ya leídos y devuelve los indicadores (se prueba sin base de datos)."""
    activos = [e for e in expedientes if e.estado != EstadoExpediente.archivado]
    vencido = _vencidos(expedientes, hoy)
    en_etapa = {e.id: _dias(ultimo_cambio.get(e.id, e.creado_en), ahora) for e in expedientes}
    edad = {e.id: _dias(e.creado_en, ahora) for e in expedientes}
    por_estado = _por_estado(expedientes, en_etapa)
    return {
        "fecha": hoy.isoformat(),
        "total": len(expedientes),
        "activos": len(activos),
        "vencidos": len(vencido),
        "antiguedad_promedio_dias": _promedio([edad[e.id] for e in activos]),
        "cuello_de_botella": _cuello_de_botella(por_estado),
        "por_estado": por_estado,
        "por_juez": _por_juez(activos, vencido, edad, jueces),
        "mas_antiguos": _mas_antiguos(activos, edad, en_etapa, vencido, jueces),
    }


@router.get("/congestion")
def panel_congestion(db: Session = Depends(get_db), _: Usuario = Depends(requiere_rol(Rol.admin))):
    expedientes = db.query(Expediente).all()
    ultimo = dict(db.query(Actuacion.expediente_id, func.max(Actuacion.fecha))
                  .filter(Actuacion.tipo == "cambio_estado").group_by(Actuacion.expediente_id).all())
    jueces = dict(db.query(Usuario.id, Usuario.nombre).filter(Usuario.rol == Rol.juez).all())
    return calcular(expedientes, ultimo, jueces, date.today(), datetime.now(timezone.utc))
