"""Sprint 7: integridad de la bitácora (SEC-09/10/11), login sin enumeración (SEC-05),
límite en la consulta pública (SEC-07), DEF-03, DEF-05, Alembic y desbloqueo por consola."""
import hashlib
import threading
from datetime import date, timedelta

from conftest import PASSWORD


def _crear(client, tokens, ids, **extra):
    body = {"materia": "civil", "demandante": "S7 Demandante", "demandado": "S7 Demandado",
            "juez_id": ids["juez1"], **extra}
    r = client.post("/api/expedientes", json=body, headers=tokens["secretario1"])
    assert r.status_code == 201, r.text
    return r.json()


# --- SEC-09 / SEC-10: hash v2 con HMAC que cubre expediente_id e ip ---

def test_sec09_mover_un_registro_de_expediente_rompe_la_cadena(client, tokens, ids):
    from app.db import SessionLocal
    from app.models import Auditoria

    exp = _crear(client, tokens, ids)
    with SessionLocal() as db:
        reg = db.query(Auditoria).filter_by(expediente_id=exp["id"]).first()
        reg_id, original = reg.id, reg.expediente_id
        reg.expediente_id = 1  # lo "esconde" en otro expediente
        db.commit()
    rota = client.get("/api/auditoria/verificar", headers=tokens["admin1"]).json()
    with SessionLocal() as db:
        db.get(Auditoria, reg_id).expediente_id = original
        db.commit()
    assert rota["integra"] is False and rota["roto_en_id"] == reg_id
    assert client.get("/api/auditoria/verificar", headers=tokens["admin1"]).json()["integra"] is True


def test_sec10_sin_la_clave_no_se_puede_recalcular_el_hash(client, tokens, ids, monkeypatch):
    from app import audit
    from app.db import SessionLocal
    from app.models import Auditoria

    exp = _crear(client, tokens, ids)
    with SessionLocal() as db:
        reg = db.query(Auditoria).filter_by(expediente_id=exp["id"]).first()
        assert reg.version == 2
        contenido = "|".join([audit._contenido_v1(reg), str(reg.expediente_id), reg.ip, "v2"])
        assert hashlib.sha256(contenido.encode()).hexdigest() != reg.hash  # un SHA-256 sin clave no lo reproduce
        monkeypatch.setattr(audit, "AUDIT_KEY", "otra-clave")
        assert audit._calcular_hash(reg) != reg.hash


def test_sec11_escrituras_concurrentes_no_bifurcan_la_cadena(client, tokens):
    from app import audit
    from app.db import SessionLocal

    errores = []

    def escribir(i):
        try:
            with SessionLocal() as db:
                audit.registrar(db, usuario=f"hilo{i}", accion="PRUEBA_CONCURRENCIA", entidad="prueba", entidad_id=i)
                db.commit()
        except Exception as e:  # noqa: BLE001
            errores.append(e)

    hilos = [threading.Thread(target=escribir, args=(i,)) for i in range(12)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert not errores
    r = client.get("/api/auditoria/verificar", headers=tokens["admin1"]).json()
    assert r["integra"] is True and r["registros_v2"] > 0


# --- SEC-05: sin enumeración en el login ---

def test_sec05_cuenta_bloqueada_responde_401_sin_la_clave(client, tokens):
    client.post("/api/usuarios", headers=tokens["admin1"], json={
        "username": "unit_enum", "nombre": "Unit Enum", "password": PASSWORD, "rol": "juez"})
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "unit_enum", "password": "mala"})
    sin_clave = client.post("/api/auth/login", json={"username": "unit_enum", "password": "otra-mala"})
    inexistente = client.post("/api/auth/login", json={"username": "no_existe_s7", "password": "otra-mala"})
    assert sin_clave.status_code == inexistente.status_code == 401
    assert sin_clave.json() == inexistente.json()
    assert client.post("/api/auth/login", json={"username": "unit_enum", "password": PASSWORD}).status_code == 423
    client.post("/api/auth/login", json={"username": "juez1", "password": PASSWORD})  # limpia el contador de la IP


# --- SEC-07: límite de consultas públicas fallidas por IP ---

def test_sec07_consulta_publica_429_tras_muchos_fallos(client):
    from app.routers.publico import fallos_consulta

    fallos_consulta.limpiar("testclient")
    original = fallos_consulta.maximo
    fallos_consulta.maximo = 3
    try:
        for _ in range(3):
            r = client.get("/api/publico/consulta", params={"numero": "EXP-2026-999999", "codigo": "ZZZZZZZZ"})
            assert r.status_code == 404
        r = client.get("/api/publico/consulta", params={"numero": "EXP-2026-000001", "codigo": "A1B2C3D4"})
        assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    finally:
        fallos_consulta.maximo = original
        fallos_consulta.limpiar("testclient")


# --- DEF-03 y DEF-05 ---

def test_def03_rango_de_plazos_invertido_422(client, tokens):
    hoy = date.today()
    r = client.get("/api/expedientes", headers=tokens["secretario1"],
                   params={"plazo_desde": (hoy + timedelta(days=5)).isoformat(), "plazo_hasta": hoy.isoformat()})
    assert r.status_code == 422


def test_def05_abogado_solo_escritos_y_no_en_cerrados(client, tokens, ids):
    exp = _crear(client, tokens, ids, abogado_id=ids["abogado1"])
    url = f"/api/expedientes/{exp['id']}/actuaciones"
    falso = client.post(url, headers=tokens["abogado1"],
                        json={"tipo": "cambio_estado", "detalle": "radicado -> con_sentencia: falso"})
    assert falso.status_code == 422
    assert client.post(url, headers=tokens["abogado1"], json={"tipo": "auto", "detalle": "Auto falso"}).status_code == 422
    assert client.post(url, headers=tokens["abogado1"], json={"tipo": "escrito", "detalle": "Contestacion"}).status_code == 201
    estado = f"/api/expedientes/{exp['id']}/estado"
    for e in ("en_tramite", "con_sentencia"):
        client.post(estado, json={"estado": e, "motivo": f"Paso a {e}"}, headers=tokens["juez1"])
    assert client.post(url, headers=tokens["abogado1"], json={"tipo": "escrito", "detalle": "Tarde"}).status_code == 409
    notif = client.post(url, headers=tokens["secretario1"], json={"tipo": "notificacion", "detalle": "Se notifica la sentencia"})
    assert notif.status_code == 201


# --- Alembic y operación ---

def test_alembic_crea_el_mismo_esquema_que_los_modelos(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    from app import migraciones
    from app.db import Base

    url = f"sqlite:///{(tmp_path / 'alembic.db').as_posix()}"
    monkeypatch.setattr("app.config.DATABASE_URL", url)
    cfg = Config(str(migraciones.RAIZ / "alembic.ini"))
    cfg.attributes["configurar_logs"] = False
    command.upgrade(cfg, "head")
    motor = create_engine(url)
    insp = inspect(motor)
    assert set(insp.get_table_names()) - {"alembic_version"} == set(Base.metadata.tables)
    for nombre, tabla in Base.metadata.tables.items():
        assert {c["name"] for c in insp.get_columns(nombre)} == {c.name for c in tabla.columns}
    motor.dispose()


def test_desbloqueo_por_consola(client, tokens, capsys):
    from app.desbloquear import main

    client.post("/api/usuarios", headers=tokens["admin1"], json={
        "username": "unit_consola", "nombre": "Unit Consola", "password": PASSWORD, "rol": "juez"})
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "unit_consola", "password": "mala"})
    assert main(["desbloquear", "unit_consola"]) == 0
    assert main(["desbloquear", "nadie_xyz"]) == 1
    assert main(["desbloquear"]) == 2
    assert client.post("/api/auth/login", json={"username": "unit_consola", "password": PASSWORD}).status_code == 200
    assert "desbloqueado" in capsys.readouterr().out


def test_respuestas_de_la_api_no_se_guardan_en_cache(client, tokens):
    r = client.get("/api/expedientes", headers=tokens["secretario1"])
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
