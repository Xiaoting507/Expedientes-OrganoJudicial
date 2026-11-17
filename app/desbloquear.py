"""SEC-04: desbloqueo por consola (vía fuera de banda si todos los admin quedan bloqueados).

Uso:  python -m app.desbloquear admin1
"""
import sys

from .db import SessionLocal
from .models import Usuario


def desbloquear(username: str) -> bool:
    with SessionLocal() as db:
        u = db.query(Usuario).filter_by(username=username).first()
        if u is None:
            return False
        u.activo, u.intentos_fallidos, u.bloqueado_hasta = True, 0, None
        from . import audit

        audit.registrar(db, usuario="consola", accion="DESBLOQUEAR_USUARIO", entidad="usuario", entidad_id=u.id)
        db.commit()
        return True


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Uso: python -m app.desbloquear <usuario>")
        return 2
    if desbloquear(argv[1]):
        print(f"Usuario {argv[1]} desbloqueado.")
        return 0
    print(f"No existe el usuario {argv[1]}.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
