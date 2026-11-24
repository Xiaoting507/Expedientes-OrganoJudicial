"""PB-02 — HU-02: Como usuario del sistema quiero iniciar sesión con mi rol.

SEC-04 (Sprint 6): el bloqueo por 5 intentos dura BLOQUEO_MINUTOS (15) y expira solo,
así nadie puede dejar fuera al administrador para siempre. Además hay un límite de
fallos por IP (429 con Retry-After) contra el password spraying.

SEC-05 (Sprint 7): sin enumeración de usuarios. Un usuario inexistente gasta el mismo
PBKDF2 que uno real, y el estado de bloqueo o desactivación solo se revela a quien
ya demostró conocer la contraseña; a los demás se les responde siempre 401 genérico.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import audit
from ..config import BLOQUEO_MINUTOS, LOGIN_MAX_FALLOS_IP
from ..db import get_db
from ..limites import VentanaFallos
from ..models import Usuario
from ..schemas import LoginIn, TokenOut, UsuarioOut
from ..security import MAX_INTENTOS, crear_token, hash_password, usuario_actual, verificar_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

fallos_por_ip = VentanaFallos(maximo=LOGIN_MAX_FALLOS_IP, segundos=BLOQUEO_MINUTOS * 60)
_HASH_FICTICIO = hash_password("usuario-inexistente")  # SEC-05: mismo costo de PBKDF2 que un usuario real


def _ip(request: Request) -> str:
    return request.client.host if request.client else "-"


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)  # SQLite guarda sin zona


def minutos_restantes(usuario: Usuario, ahora: datetime) -> int:
    if usuario.bloqueado_hasta is None:
        return 0
    faltan = (_utc(usuario.bloqueado_hasta) - ahora).total_seconds()
    return 0 if faltan <= 0 else int(faltan // 60) + 1


@router.post("/login", response_model=TokenOut)
def login(datos: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = _ip(request)
    espera = fallos_por_ip.excedido(ip)
    if espera:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Demasiados intentos desde esta conexión. Intente en {espera // 60 + 1} minutos.",
                            headers={"Retry-After": str(espera)})

    usuario = db.query(Usuario).filter_by(username=datos.username).first()
    error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")

    if usuario is None:
        verificar_password(datos.password, _HASH_FICTICIO)
        fallos_por_ip.registrar(ip)
        audit.registrar(db, usuario=datos.username, accion="LOGIN_FALLIDO", entidad="usuario",
                        entidad_id="-", request=request)
        db.commit()
        raise error

    ahora = datetime.now(timezone.utc)
    clave_ok = verificar_password(datos.password, usuario.password_hash)
    faltan = minutos_restantes(usuario, ahora)

    if not usuario.activo or faltan:
        fallos_por_ip.registrar(ip)
        audit.registrar(db, usuario=datos.username, accion="LOGIN_FALLIDO", entidad="usuario",
                        entidad_id=usuario.id, request=request)
        db.commit()
        if not clave_ok:  # SEC-05: sin la clave no se revela si la cuenta está bloqueada
            raise error
        if not usuario.activo:
            raise HTTPException(status.HTTP_423_LOCKED, "Cuenta desactivada. Contacte al administrador")
        raise HTTPException(status.HTTP_423_LOCKED,
                            f"Cuenta bloqueada temporalmente por intentos fallidos. Intente en {faltan} minutos.",
                            headers={"Retry-After": str(faltan * 60)})
    if usuario.bloqueado_hasta is not None:  # el bloqueo ya venció: empieza de cero
        usuario.bloqueado_hasta, usuario.intentos_fallidos = None, 0

    if not clave_ok:
        fallos_por_ip.registrar(ip)
        usuario.intentos_fallidos += 1
        accion = "LOGIN_FALLIDO"
        if usuario.intentos_fallidos >= MAX_INTENTOS:
            usuario.bloqueado_hasta = ahora + timedelta(minutes=BLOQUEO_MINUTOS)
            accion = "CUENTA_BLOQUEADA"
        audit.registrar(db, usuario=datos.username, accion=accion, entidad="usuario",
                        entidad_id=usuario.id, request=request)
        db.commit()
        raise error

    usuario.intentos_fallidos = 0
    fallos_por_ip.limpiar(ip)
    audit.registrar(db, usuario=usuario.username, accion="LOGIN_OK", entidad="usuario",
                    entidad_id=usuario.id, request=request)
    db.commit()
    return TokenOut(access_token=crear_token(usuario), rol=usuario.rol, nombre=usuario.nombre)


@router.get("/me", response_model=UsuarioOut)
def yo(usuario: Usuario = Depends(usuario_actual)):
    return usuario
