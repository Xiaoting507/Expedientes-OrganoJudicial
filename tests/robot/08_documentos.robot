*** Settings ***
Documentation     HU-10 (Sprint 7) — Adjuntar PDF al expediente con huella SHA-256.
...               RN-10.1 solo PDF y máx. 10 MB · RN-10.2 huella verificable · RN-10.3 permisos del expediente
...               · RN-10.4 todo queda en la bitácora.
Resource          resources/common.resource
Suite Setup       Preparar Suite
Test Tags         HU-10    PB-01    documentos

*** Variables ***
${PDF_TEXTO}      %PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n

*** Keywords ***
Preparar Suite
    Abrir Sesion API
    ${hs}=    Login Como    secretario1
    ${hj}=    Login Como    juez1
    ${hj2}=    Login Como    juez2
    ${ha}=    Login Como    abogado1
    Set Suite Variable    ${H_SEC}    ${hs}
    Set Suite Variable    ${H_JUEZ}    ${hj}
    Set Suite Variable    ${H_JUEZ2}    ${hj2}
    Set Suite Variable    ${H_ABG}    ${ha}

Archivo PDF
    [Arguments]    ${extra}=robot    ${nombre}=escrito-robot.pdf
    ${bytes}=    Evaluate    ($PDF_TEXTO + "% " + $extra + "\\n").encode()
    ${archivo}=    Evaluate    {"archivo": ($nombre, $bytes, "application/pdf")}
    RETURN    ${archivo}    ${bytes}

Subir PDF
    [Arguments]    ${headers}    ${exp_id}    ${archivos}    ${esperado}=201
    ${resp}=    POST On Session    api    /api/expedientes/${exp_id}/documentos    files=${archivos}
    ...    headers=${headers}    expected_status=${esperado}
    RETURN    ${resp}

*** Test Cases ***
Secretario adjunta un PDF y el juez lo descarga integro
    ${exp}=    Crear Expediente De Prueba    ${H_SEC}
    ${archivos}    ${bytes}=    Archivo PDF    integro
    ${resp}=    Subir PDF    ${H_SEC}    ${exp}[id]    ${archivos}
    ${esperado}=    Evaluate    __import__('hashlib').sha256($bytes).hexdigest()
    Should Be Equal    ${resp.json()}[sha256]    ${esperado}
    ${desc}=    GET On Session    api    /api/expedientes/${exp}[id]/documentos/${resp.json()}[id]    headers=${H_JUEZ}    expected_status=200
    Should Be Equal    ${desc.content}    ${bytes}
    Should Be Equal    ${desc.headers}[X-Content-SHA256]    ${esperado}

Archivo que no es PDF se rechaza aunque se llame .pdf
    ${exp}=    Crear Expediente De Prueba    ${H_SEC}
    ${falso}=    Evaluate    {"archivo": ("virus.pdf", b"MZ ejecutable", "application/pdf")}
    Subir PDF    ${H_SEC}    ${exp}[id]    ${falso}    esperado=415

Juez ajeno no puede adjuntar ni listar documentos
    ${exp}=    Crear Expediente De Prueba    ${H_SEC}
    ${archivos}    ${bytes}=    Archivo PDF    ajeno
    Subir PDF    ${H_JUEZ2}    ${exp}[id]    ${archivos}    esperado=403
    GET On Session    api    /api/expedientes/${exp}[id]/documentos    headers=${H_JUEZ2}    expected_status=403

Expediente archivado no admite documentos nuevos
    ${exp}=    Crear Expediente De Prueba    ${H_SEC}
    ${body}=    Create Dictionary    estado=archivado    motivo=Archivo definitivo
    POST On Session    api    /api/expedientes/${exp}[id]/estado    json=${body}    headers=${H_JUEZ}    expected_status=200
    ${archivos}    ${bytes}=    Archivo PDF    archivado
    Subir PDF    ${H_SEC}    ${exp}[id]    ${archivos}    esperado=409

Subida queda en la bitacora del expediente con su huella
    ${exp}=    Crear Expediente De Prueba    ${H_SEC}
    ${archivos}    ${bytes}=    Archivo PDF    bitacora
    ${resp}=    Subir PDF    ${H_SEC}    ${exp}[id]    ${archivos}
    ${hist}=    GET On Session    api    /api/expedientes/${exp}[id]/auditoria    headers=${H_SEC}    expected_status=200
    ${acciones}=    Evaluate    [r["accion"] for r in $hist.json()]
    List Should Contain Value    ${acciones}    SUBIR_DOCUMENTO
    Should Contain    ${hist.json()}[-1][despues]    ${resp.json()}[sha256]
