"""HU-10 (Sprint 7): adjuntar PDF al expediente con huella SHA-256."""
import hashlib
from pathlib import Path

PDF = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"


def _crear(client, tokens, ids, **extra):
    body = {"materia": "civil", "demandante": "Doc Demandante", "demandado": "Doc Demandado",
            "juez_id": ids["juez1"], **extra}
    r = client.post("/api/expedientes", json=body, headers=tokens["secretario1"])
    assert r.status_code == 201, r.text
    return r.json()


def _subir(client, headers, exp_id, contenido=PDF, nombre="escrito.pdf"):
    return client.post(f"/api/expedientes/{exp_id}/documentos", headers=headers,
                       files={"archivo": (nombre, contenido, "application/pdf")})


def test_hu10_subir_pdf_guarda_la_huella_sha256(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    r = _subir(client, tokens["secretario1"], exp["id"])
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["sha256"] == hashlib.sha256(PDF).hexdigest() and doc["tamano"] == len(PDF) and doc["nombre"] == "escrito.pdf"
    lista = client.get(f"/api/expedientes/{exp['id']}/documentos", headers=tokens["juez1"]).json()
    assert [d["id"] for d in lista] == [doc["id"]]


def test_hu10_rechaza_lo_que_no_es_pdf_aunque_diga_pdf(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    r = _subir(client, tokens["secretario1"], exp["id"], contenido=b"MZ\x90\x00 ejecutable", nombre="falso.pdf")
    assert r.status_code == 415


def test_hu10_rechaza_pdf_demasiado_grande(client, tokens, ids):
    from app.routers.documentos import MAX_BYTES

    exp = _crear(client, tokens, ids)
    r = _subir(client, tokens["secretario1"], exp["id"], contenido=PDF + b"0" * MAX_BYTES)
    assert r.status_code == 413


def test_hu10_descarga_integra_con_cabecera_sha256(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    doc = _subir(client, tokens["secretario1"], exp["id"]).json()
    r = client.get(f"/api/expedientes/{exp['id']}/documentos/{doc['id']}", headers=tokens["juez1"])
    assert r.status_code == 200 and r.content == PDF
    assert r.headers["x-content-sha256"] == doc["sha256"] and r.headers["content-type"] == "application/pdf"


def test_hu10_detecta_archivo_alterado_y_lo_registra(client, tokens, ids):
    from app.routers.documentos import _ruta

    exp = _crear(client, tokens, ids)
    contenido = PDF + b"% unico alterado\n"
    doc = _subir(client, tokens["secretario1"], exp["id"], contenido=contenido).json()
    Path(_ruta(doc["sha256"])).write_bytes(contenido + b"manipulado")
    url = f"/api/expedientes/{exp['id']}/documentos/{doc['id']}"
    assert client.get(url + "/verificar", headers=tokens["juez1"]).json()["integro"] is False
    assert client.get(url, headers=tokens["juez1"]).status_code == 409
    historial = client.get(f"/api/expedientes/{exp['id']}/auditoria", headers=tokens["secretario1"]).json()
    acciones = [a["accion"] for a in historial]
    assert "SUBIR_DOCUMENTO" in acciones and "DOCUMENTO_ALTERADO" in acciones


def test_hu10_permisos_juez_ajeno_y_admin(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    assert _subir(client, tokens["juez2"], exp["id"]).status_code == 403
    assert _subir(client, tokens["admin1"], exp["id"]).status_code == 403
    assert client.get(f"/api/expedientes/{exp['id']}/documentos", headers=tokens["juez2"]).status_code == 403


def test_hu10_abogado_solo_en_sus_casos_abiertos(client, tokens, ids):
    propio = _crear(client, tokens, ids, abogado_id=ids["abogado1"])
    ajeno = _crear(client, tokens, ids)
    assert _subir(client, tokens["abogado1"], propio["id"], contenido=PDF + b"% abogado\n").status_code == 201
    assert _subir(client, tokens["abogado1"], ajeno["id"]).status_code == 403


def test_hu10_archivado_no_admite_documentos(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    client.post(f"/api/expedientes/{exp['id']}/estado", json={"estado": "archivado", "motivo": "Archivo definitivo"},
                headers=tokens["juez1"])
    assert _subir(client, tokens["secretario1"], exp["id"]).status_code == 409


def test_hu10_nombre_de_archivo_saneado(client, tokens, ids):
    exp = _crear(client, tokens, ids)
    r = _subir(client, tokens["secretario1"], exp["id"], contenido=PDF + b"% nombre\n", nombre="../../etc/passwd")
    assert r.status_code == 201 and "/" not in r.json()["nombre"] and r.json()["nombre"].endswith(".pdf")
