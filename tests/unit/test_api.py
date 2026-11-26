"""Endpoints clave con TestClient y BD temporal (ver conftest)."""
from datetime import date, timedelta

from conftest import PASSWORD


def _crear(client, tokens, ids, **extra):
    body = {"materia": "civil", "demandante": "Unit Demandante", "demandado": "Unit Demandado",
            "juez_id": ids["juez1"], **extra}
    r = client.post("/api/expedientes", json=body, headers=tokens["secretario1"])
    assert r.status_code == 201, r.text
    return r.json()


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_cabeceras_de_seguridad(client):
    h = client.get("/healthz").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"


def test_login_ok_y_fallido(client):
    assert client.post("/api/auth/login", json={"username": "juez1", "password": PASSWORD}).status_code == 200
    assert client.post("/api/auth/login", json={"username": "juez1", "password": "mala"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "nadie", "password": "x"}).status_code == 401


def test_sin_token_401_y_token_basura_401(client):
    assert client.get("/api/expedientes").status_code == 401
    assert client.get("/api/expedientes", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_crear_expediente_solo_secretario(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    assert exp["estado"] == "radicado" and len(exp["codigo_consulta"]) == 8
    body = {"materia": "civil", "demandante": "Abc Def", "demandado": "Ghi Jkl"}
    for u in ("juez1", "abogado1", "admin1"):
        assert client.post("/api/expedientes", json=body, headers=tokens[u]).status_code == 403


def test_crear_expediente_con_juez_invalido_422(client, tokens, ids):
    body = {"materia": "civil", "demandante": "Abc Def", "demandado": "Ghi Jkl", "juez_id": ids["secretario1"]}
    assert client.post("/api/expedientes", json=body, headers=tokens["secretario1"]).status_code == 422


def test_patch_juez_no_juez_422(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    r = client.patch(f"/api/expedientes/{exp['id']}", json={"juez_id": ids["abogado1"]}, headers=tokens["secretario1"])
    assert r.status_code == 422


def test_juez_ajeno_403_y_propio_200(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    assert client.get(f"/api/expedientes/{exp['id']}", headers=tokens["juez2"]).status_code == 403
    assert client.get(f"/api/expedientes/{exp['id']}", headers=tokens["juez1"]).status_code == 200


def test_cambio_estado_valida_motivo_y_rol(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    url = f"/api/expedientes/{exp['id']}/estado"
    assert client.post(url, json={"estado": "en_tramite", "motivo": "ok"}, headers=tokens["juez1"]).status_code == 422
    assert client.post(url, json={"estado": "en_tramite", "motivo": "Admitida la demanda"},
                       headers=tokens["secretario1"]).status_code == 403
    r = client.post(url, json={"estado": "en_tramite", "motivo": "Admitida la demanda"}, headers=tokens["juez1"])
    assert r.status_code == 200 and r.json()["estado"] == "en_tramite"


def test_abogado_solo_ve_los_suyos(client, tokens, ids):
    propio = _crear(client, tokens, ids, abogado_id=ids["abogado1"])
    ajeno = _crear(client, tokens, ids)
    lista = client.get("/api/expedientes", headers=tokens["abogado1"]).json()
    assert propio["id"] in [e["id"] for e in lista] and ajeno["id"] not in [e["id"] for e in lista]
    assert client.get(f"/api/expedientes/{ajeno['id']}", headers=tokens["abogado1"]).status_code == 403
    r = client.post(f"/api/expedientes/{propio['id']}/actuaciones", headers=tokens["abogado1"],
                    json={"tipo": "escrito", "detalle": "Contestacion"})
    assert r.status_code == 201
    assert client.get("/api/auditoria", headers=tokens["abogado1"]).status_code == 403


def test_filtros_estado_invalido_422_y_materia(client, tokens, ids):
    assert client.get("/api/expedientes?estado=xyz", headers=tokens["secretario1"]).status_code == 422
    _crear(client, tokens, ids, materia="penal-unit")
    lista = client.get("/api/expedientes?materia=penal-unit", headers=tokens["secretario1"]).json()
    assert lista and all(e["materia"] == "penal-unit" for e in lista)


def test_alertas_excluyen_archivados(client, tokens, ids):
    ayer = (date.today() - timedelta(days=1)).isoformat()
    exp = _crear(client, tokens, ids, fecha_limite=ayer)
    assert exp["id"] in [e["id"] for e in client.get("/api/expedientes/alertas", headers=tokens["secretario1"]).json()]
    client.post(f"/api/expedientes/{exp['id']}/estado", json={"estado": "archivado", "motivo": "Archivo definitivo"},
                headers=tokens["juez1"])
    assert exp["id"] not in [e["id"] for e in client.get("/api/expedientes/alertas", headers=tokens["secretario1"]).json()]


def test_historial_por_expediente_y_permisos(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    client.get(f"/api/expedientes/{exp['id']}", headers=tokens["juez1"])
    url = f"/api/expedientes/{exp['id']}/auditoria"
    r = client.get(url, headers=tokens["secretario1"])
    assert r.status_code == 200
    acciones = [x["accion"] for x in r.json()]
    # RN-09.2 (Sprint 9): por defecto el historial muestra solo cambios; las consultas, a pedido
    assert acciones[0] == "CREAR_EXPEDIENTE" and "CONSULTAR_EXPEDIENTE" not in acciones
    con = client.get(url, params={"incluir_consultas": "true"}, headers=tokens["secretario1"]).json()
    assert "CONSULTAR_EXPEDIENTE" in [x["accion"] for x in con]
    assert all(x["expediente_id"] == exp["id"] for x in r.json())
    assert client.get(url, headers=tokens["juez2"]).status_code == 403
    assert client.get(url, headers=tokens["abogado1"]).status_code == 403


def test_bitacora_solo_admin_y_cadena_integra(client, tokens):
    assert client.get("/api/auditoria", headers=tokens["secretario1"]).status_code == 403
    r = client.get("/api/auditoria/verificar", headers=tokens["admin1"]).json()
    assert r["integra"] is True and r["registros"] > 0


def test_consulta_publica(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    ok = client.post("/api/publico/consulta", json={"numero": exp["numero"], "codigo": exp["codigo_consulta"]})
    assert ok.status_code == 200 and "demandante" not in ok.json()
    mal = client.post("/api/publico/consulta", json={"numero": exp["numero"], "codigo": "ZZZZZZZZ"})
    inex = client.post("/api/publico/consulta", json={"numero": "EXP-0000-000000", "codigo": "ZZZZZZZZ"})
    assert mal.status_code == inex.status_code == 404 and mal.json() == inex.json()


# --- Defectos cerrados en el Sprint 6 (antes xfail) ---

def test_def01_no_se_puede_reabrir_un_archivado_a_radicado(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    url = f"/api/expedientes/{exp['id']}/estado"
    assert client.post(url, json={"estado": "archivado", "motivo": "Archivo definitivo"}, headers=tokens["juez1"]).status_code == 200
    r = client.post(url, json={"estado": "radicado", "motivo": "Intento de reabrir"}, headers=tokens["juez1"])
    assert r.status_code == 409


def test_def02_numero_no_se_duplica_si_hay_huecos(client, tokens, ids):
    from app.db import SessionLocal
    from app.models import Expediente

    a = _crear(client, tokens, ids)
    _crear(client, tokens, ids)
    with SessionLocal() as db:  # simula un hueco (borrado/archivado fisico por DBA)
        db.query(Expediente).filter(Expediente.id == a["id"]).delete()
        db.commit()
    body = {"materia": "civil", "demandante": "Hueco Uno", "demandado": "Hueco Dos"}
    r = client.post("/api/expedientes", json=body, headers=tokens["secretario1"])
    assert r.status_code == 201


def test_def01_no_hay_sentencia_sin_admitir_la_demanda(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    url = f"/api/expedientes/{exp['id']}/estado"
    r = client.post(url, json={"estado": "con_sentencia", "motivo": "Sentencia directa"}, headers=tokens["juez1"])
    assert r.status_code == 409


def test_def01_409_informa_los_estados_permitidos(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    url = f"/api/expedientes/{exp['id']}/estado"
    r = client.post(url, json={"estado": "en_audiencia", "motivo": "Saltar el tramite"}, headers=tokens["juez1"])
    assert r.status_code == 409
    assert sorted(r.json()["detail"]["permitidos"]) == ["archivado", "en_tramite"]


def test_def01_camino_completo_permitido(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    url = f"/api/expedientes/{exp['id']}/estado"
    for estado in ("en_tramite", "en_audiencia", "con_sentencia", "archivado"):
        r = client.post(url, json={"estado": estado, "motivo": f"Paso a {estado}"}, headers=tokens["juez1"])
        assert r.status_code == 200, (estado, r.text)
