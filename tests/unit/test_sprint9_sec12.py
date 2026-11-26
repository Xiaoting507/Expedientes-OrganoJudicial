"""Sprint 9: SEC-12 (eventos anónimos fuera de la cadena) y RN-09.2 (historial solo con cambios)."""
from datetime import timedelta

from app import audit
from app.models import EventoAcceso, ahora


def _cadena(client, tokens):
    return client.get("/api/auditoria/verificar", headers=tokens["admin1"]).json()


def _accesos(client, tokens, **params):
    r = client.get("/api/auditoria/accesos", params=params, headers=tokens["admin1"])
    assert r.status_code == 200, r.text
    return r.json()


def _crear(client, tokens, ids):
    body = {"materia": "civil", "demandante": "S9 Demandante", "demandado": "S9 Demandado", "juez_id": ids["juez1"]}
    r = client.post("/api/expedientes", json=body, headers=tokens["secretario1"])
    assert r.status_code == 201, r.text
    return r.json()


def test_sec12_consultas_del_ciudadano_no_crecen_la_cadena(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    antes = _cadena(client, tokens)["registros"]
    assert client.post("/api/publico/consulta", json={"numero": exp["numero"], "codigo": exp["codigo_consulta"]}).status_code == 200
    assert client.post("/api/publico/consulta", json={"numero": exp["numero"], "codigo": "NOPE0000"}).status_code == 404
    despues = _cadena(client, tokens)
    assert despues["registros"] == antes and despues["integra"] is True
    refs = [(e["accion"], e["referencia"]) for e in _accesos(client, tokens)]
    assert ("CONSULTA_PUBLICA", exp["numero"]) in refs
    assert ("CONSULTA_PUBLICA_FALLIDA", exp["numero"]) in refs


def test_sec12_login_de_usuario_inexistente_va_fuera_de_la_cadena(client, tokens):
    antes = _cadena(client, tokens)["registros"]
    r = client.post("/api/auth/login", json={"username": "intruso_s9", "password": "x"})
    assert r.status_code == 401
    assert _cadena(client, tokens)["registros"] == antes
    fallidos = _accesos(client, tokens, accion="LOGIN_FALLIDO")
    assert any(e["usuario"] == "intruso_s9" for e in fallidos)
    assert all(e["accion"] == "LOGIN_FALLIDO" for e in fallidos)


def test_sec12_fallo_contra_una_cuenta_real_sigue_en_la_cadena(client, tokens):
    """Un intento contra una cuenta existente sí es evidencia sobre esa cuenta: se encadena."""
    antes = _cadena(client, tokens)["registros"]
    assert client.post("/api/auth/login", json={"username": "abogado1", "password": "mala"}).status_code == 401
    assert _cadena(client, tokens)["registros"] == antes + 1
    ultimo = client.get("/api/auditoria", params={"limite": 1}, headers=tokens["admin1"]).json()[0]
    assert ultimo["accion"] == "LOGIN_FALLIDO" and ultimo["usuario"] == "abogado1"
    client.post("/api/auth/login", json={"username": "abogado1", "password": "Demo-Judicial-2026"})  # limpia el contador


def test_sec12_solo_el_administrador_ve_los_accesos(client, tokens):
    assert client.get("/api/auditoria/accesos").status_code == 401
    for u in ("secretario1", "juez1", "abogado1"):
        assert client.get("/api/auditoria/accesos", headers=tokens[u]).status_code == 403


def test_sec12_rotacion_borra_lo_que_pasa_la_retencion(db_mem):
    viejo = EventoAcceso(fecha=ahora() - timedelta(days=400), accion="CONSULTA_PUBLICA", usuario="ciudadano",
                         referencia="EXP-VIEJO", ip="1.1.1.1")
    reciente = EventoAcceso(fecha=ahora() - timedelta(days=1), accion="CONSULTA_PUBLICA", usuario="ciudadano",
                            referencia="EXP-RECIENTE", ip="1.1.1.1")
    db_mem.add_all([viejo, reciente])
    db_mem.commit()
    audit.registrar_acceso(db_mem, accion="LOGIN_FALLIDO", usuario="x" * 80, referencia="R" * 50)
    db_mem.commit()
    refs = sorted(e.referencia for e in db_mem.query(EventoAcceso).all())
    assert refs == ["EXP-RECIENTE", "R" * 40]  # el de hace 400 días se borró; el nuevo se recorta a 40
    assert len(db_mem.query(EventoAcceso).filter_by(accion="LOGIN_FALLIDO").one().usuario) == 60


def test_rn092_historial_sin_consultas_y_con_consultas_a_pedido(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    client.get(f"/api/expedientes/{exp['id']}", headers=tokens["juez1"])
    url = f"/api/expedientes/{exp['id']}/auditoria"
    solo_cambios = [x["accion"] for x in client.get(url, headers=tokens["juez1"]).json()]
    todo = [x["accion"] for x in client.get(url, params={"incluir_consultas": "true"}, headers=tokens["juez1"]).json()]
    assert solo_cambios == ["CREAR_EXPEDIENTE"]
    assert todo.count("CONSULTAR_EXPEDIENTE") >= 1 and todo[0] == "CREAR_EXPEDIENTE"
