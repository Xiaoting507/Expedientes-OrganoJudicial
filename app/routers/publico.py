"""PB-05 — Consulta pública: el ciudadano ve SOLO el estado de su proceso.

Requiere número de expediente + código de consulta (entregado por el secretario).
No expone nombres de las partes ni el detalle de las actuaciones.

SEC-07 (Sprint 7): máximo CONSULTA_MAX_FALLOS_IP consultas fallidas por IP en 15 minutos;
después responde 429 con Retry-After (frena la fuerza bruta sobre el código de 8 caracteres).

SEC-08 (Sprint 8): el código de consulta es una credencial y ya no viaja en la URL. Se envía en el
cuerpo de un POST, así no queda en los access logs de uvicorn o del Ingress ni en el historial del
navegador. El GET anterior responde 405.

SEC-12 (Sprint 9): las consultas del ciudadano son anónimas y ya no entran en la cadena de la
bitácora; quedan en eventos_acceso (sin hash, con rotación).
"""
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import audit
from ..config import CONSULTA_MAX_FALLOS_IP
from ..db import get_db
from ..limites import VentanaFallos
from ..models import Expediente
from ..schemas import ConsultaPublicaIn, ConsultaPublicaOut

router = APIRouter(prefix="/api/publico", tags=["consulta pública"])
fallos_consulta = VentanaFallos(maximo=CONSULTA_MAX_FALLOS_IP, segundos=15 * 60)


@router.post("/consulta", response_model=ConsultaPublicaOut)
def consultar(datos: ConsultaPublicaIn, request: Request, db: Session = Depends(get_db)):
    numero, codigo = datos.numero, datos.codigo
    ip = request.client.host if request.client else "-"
    espera = fallos_consulta.excedido(ip)
    if espera:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Demasiadas consultas fallidas. Intente en {espera // 60 + 1} minutos.",
                            headers={"Retry-After": str(espera)})
    exp = db.query(Expediente).filter_by(numero=numero.strip().upper()).first()
    # Mismo mensaje si no existe o si el código es incorrecto (no revelar qué expedientes existen)
    if exp is None or not hmac.compare_digest(exp.codigo_consulta, codigo.strip().upper()):
        fallos_consulta.registrar(ip)
        audit.registrar_acceso(db, accion="CONSULTA_PUBLICA_FALLIDA", usuario="ciudadano", referencia=numero,
                               request=request)
        db.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Número o código de consulta incorrecto")
    ultima = exp.actuaciones[-1].tipo if exp.actuaciones else None
    audit.registrar_acceso(db, accion="CONSULTA_PUBLICA", usuario="ciudadano", referencia=exp.numero,
                           request=request)
    db.commit()
    return ConsultaPublicaOut(numero=exp.numero, materia=exp.materia, estado=exp.estado,
                              actualizado_en=exp.actualizado_en, ultima_actuacion=ultima)
