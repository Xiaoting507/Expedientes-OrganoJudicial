"""Sprint 8: el código de consulta pública ya no viaja en la URL (SEC-08)."""


def _crear(client, tokens, ids):
    body = {"materia": "civil", "demandante": "S8 Demandante", "demandado": "S8 Demandado", "juez_id": ids["juez1"]}
    r = client.post("/api/expedientes", json=body, headers=tokens["secretario1"])
    assert r.status_code == 201, r.text
    return r.json()


def test_sec08_consulta_por_post_con_el_codigo_en_el_cuerpo(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    r = client.post("/api/publico/consulta", json={"numero": exp["numero"], "codigo": exp["codigo_consulta"]})
    assert r.status_code == 200
    assert r.json()["estado"] == "radicado"
    # Nada de la credencial queda en la URL de la petición (lo que guardan los access logs)
    assert exp["codigo_consulta"] not in str(r.request.url)


def test_sec08_el_get_con_el_codigo_en_la_url_ya_no_existe(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    r = client.get("/api/publico/consulta", params={"numero": exp["numero"], "codigo": exp["codigo_consulta"]})
    assert r.status_code == 405


def test_sec08_cuerpo_incompleto_o_demasiado_largo_422(client):
    assert client.post("/api/publico/consulta", json={"numero": "EXP-2026-000001"}).status_code == 422
    largo = {"numero": "EXP-2026-000001", "codigo": "X" * 17}
    assert client.post("/api/publico/consulta", json=largo).status_code == 422
