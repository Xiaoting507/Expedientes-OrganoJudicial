"""SEC-04 (Sprint 6): bloqueo temporal de 15 minutos y límite de fallos por IP."""
from datetime import datetime, timedelta, timezone

from conftest import PASSWORD


def _usuario(client, tokens, nombre):
    r = client.post("/api/usuarios", headers=tokens["admin1"], json={
        "username": nombre, "nombre": nombre.replace("_", " ").title(), "password": PASSWORD, "rol": "juez"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_sec04_bloqueo_temporal_con_retry_after_y_desbloqueo(client, tokens):
    uid = _usuario(client, tokens, "unit_bloqueo")
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "unit_bloqueo", "password": "mala"}).status_code == 401
    r = client.post("/api/auth/login", json={"username": "unit_bloqueo", "password": PASSWORD})
    assert r.status_code == 423
    assert int(r.headers["retry-after"]) <= 15 * 60 and "minutos" in r.json()["detail"]
    assert client.post(f"/api/usuarios/{uid}/desbloquear", headers=tokens["admin1"]).status_code == 200
    assert client.post("/api/auth/login", json={"username": "unit_bloqueo", "password": PASSWORD}).status_code == 200


def test_sec04_el_bloqueo_expira_solo(client, tokens):
    from app.db import SessionLocal
    from app.models import Usuario

    _usuario(client, tokens, "unit_expira")
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "unit_expira", "password": "mala"})
    assert client.post("/api/auth/login", json={"username": "unit_expira", "password": PASSWORD}).status_code == 423
    with SessionLocal() as db:  # simula que pasaron los 15 minutos
        u = db.query(Usuario).filter_by(username="unit_expira").one()
        u.bloqueado_hasta = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.post("/api/auth/login", json={"username": "unit_expira", "password": PASSWORD}).status_code == 200


def test_sec04_limite_de_fallos_por_ip_429(client):
    from app.routers.auth import fallos_por_ip

    fallos_por_ip.limpiar("testclient")
    maximo_original = fallos_por_ip.maximo
    fallos_por_ip.maximo = 3
    try:
        for _ in range(3):
            assert client.post("/api/auth/login", json={"username": "nadie_ip", "password": "x"}).status_code == 401
        r = client.post("/api/auth/login", json={"username": "juez1", "password": PASSWORD})
        assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    finally:
        fallos_por_ip.maximo = maximo_original
        fallos_por_ip.limpiar("testclient")
