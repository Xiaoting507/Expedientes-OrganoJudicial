"""PB-03: cadena de hashes de la bitacora (SQLite en memoria)."""
import hashlib
from datetime import timezone

from sqlalchemy import text

from app import audit
from app.models import Auditoria


def _registrar(db, n):
    for i in range(n):
        audit.registrar(db, usuario="u", accion=f"A{i}", entidad="e", entidad_id=i, despues={"i": i})
    db.commit()


def test_primer_registro_encadena_con_genesis(db_mem):
    _registrar(db_mem, 1)
    reg = db_mem.query(Auditoria).one()
    assert reg.hash_anterior == "0" * 64 == audit.GENESIS
    assert len(reg.hash) == 64


def test_registros_v1_siguen_verificandose_con_sha256(db_mem):
    """Sprint 7: los registros anteriores (v1, SHA-256 sin clave) no rompen la cadena nueva (v2, HMAC)."""
    _registrar(db_mem, 1)
    reg = db_mem.query(Auditoria).one()
    if reg.fecha.tzinfo is None:  # SQLite pierde la zona; verificar_cadena la normaliza igual
        reg.fecha = reg.fecha.replace(tzinfo=timezone.utc)
    reg.version = 1
    reg.hash = hashlib.sha256(
        "|".join([reg.hash_anterior, reg.fecha.isoformat(), reg.usuario, reg.accion, reg.entidad,
                  reg.entidad_id, reg.antes, reg.despues]).encode()
    ).hexdigest()
    db_mem.commit()
    assert reg.hash == audit._calcular_hash(reg)
    _registrar(db_mem, 2)  # los nuevos son v2 y encadenan sobre el v1
    r = audit.verificar_cadena(db_mem)
    assert r["integra"] is True and r["registros"] == 3 and r["registros_v2"] == 2


def test_cada_registro_apunta_al_hash_del_anterior(db_mem):
    _registrar(db_mem, 4)
    regs = db_mem.query(Auditoria).order_by(Auditoria.id).all()
    for previo, sig in zip(regs, regs[1:]):
        assert sig.hash_anterior == previo.hash


def test_cadena_integra(db_mem):
    _registrar(db_mem, 5)
    assert audit.verificar_cadena(db_mem) == {"integra": True, "registros": 5, "roto_en_id": None, "registros_v2": 5}


def test_cadena_vacia_es_integra(db_mem):
    assert audit.verificar_cadena(db_mem) == {"integra": True, "registros": 0, "roto_en_id": None, "registros_v2": 0}


def test_alterar_un_registro_rompe_la_cadena(db_mem):
    _registrar(db_mem, 5)
    db_mem.execute(text("UPDATE auditoria SET usuario='intruso' WHERE id=3"))
    db_mem.commit()
    assert audit.verificar_cadena(db_mem) == {"integra": False, "registros": 3, "roto_en_id": 3, "registros_v2": 2}


def test_borrar_un_registro_intermedio_rompe_la_cadena(db_mem):
    _registrar(db_mem, 4)
    db_mem.execute(text("DELETE FROM auditoria WHERE id=2"))
    db_mem.commit()
    r = audit.verificar_cadena(db_mem)
    assert r["integra"] is False and r["roto_en_id"] == 3


def test_sec09_expediente_id_e_ip_entran_en_el_hash(db_mem):
    """SEC-09 (Sprint 7): antes se podían editar sin que la verificación lo notara."""
    _registrar(db_mem, 2)
    db_mem.execute(text("UPDATE auditoria SET expediente_id=99 WHERE id=1"))
    db_mem.commit()
    assert audit.verificar_cadena(db_mem)["integra"] is False
    db_mem.execute(text("UPDATE auditoria SET expediente_id=NULL, ip='10.0.0.66' WHERE id=1"))
    db_mem.commit()
    assert audit.verificar_cadena(db_mem)["roto_en_id"] == 1


def test_registrar_guarda_expediente_id_e_ip(db_mem):
    reg = audit.registrar(db_mem, usuario="u", accion="X", entidad="expediente", entidad_id=7, expediente_id=7)
    assert reg.expediente_id == 7
    assert reg.entidad_id == "7"
    assert reg.ip == ""
