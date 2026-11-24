*** Settings ***
Documentation     PB-05 / HU-04 — Consulta pública del ciudadano y cabeceras de seguridad (PB-04).
Resource          resources/common.resource
Suite Setup       Abrir Sesion API
Test Tags         PB-05

*** Test Cases ***
Ciudadano consulta el estado con numero y codigo correctos
    ${h}=    Login Como    secretario1
    ${exp}=    Crear Expediente De Prueba    ${h}
    ${params}=    Create Dictionary    numero=${exp}[numero]    codigo=${exp}[codigo_consulta]
    ${resp}=    POST On Session    api    /api/publico/consulta    json=${params}    expected_status=200
    Should Be Equal    ${resp.json()}[estado]    radicado

La consulta publica no expone nombres de las partes
    ${h}=    Login Como    secretario1
    ${exp}=    Crear Expediente De Prueba    ${h}
    ${params}=    Create Dictionary    numero=${exp}[numero]    codigo=${exp}[codigo_consulta]
    ${resp}=    POST On Session    api    /api/publico/consulta    json=${params}
    Dictionary Should Not Contain Key    ${resp.json()}    demandante
    Dictionary Should Not Contain Key    ${resp.json()}    demandado

Codigo incorrecto devuelve 404 sin revelar si existe
    ${params}=    Create Dictionary    numero=EXP-2026-000001    codigo=XXXXXXXX
    POST On Session    api    /api/publico/consulta    json=${params}    expected_status=404

Intento de inyeccion SQL no rompe la consulta
    [Tags]    seguridad
    ${params}=    Create Dictionary    numero=' OR '1'='1    codigo=' OR '1'='1
    POST On Session    api    /api/publico/consulta    json=${params}    expected_status=404

El codigo de consulta ya no se acepta en la URL
    [Tags]    seguridad    SEC-08
    ${params}=    Create Dictionary    numero=EXP-2026-000001    codigo=XXXXXXXX
    GET On Session    api    /api/publico/consulta    params=${params}    expected_status=405

Respuestas incluyen cabeceras de seguridad
    [Tags]    PB-04    seguridad
    ${resp}=    GET On Session    api    /healthz
    Should Be Equal    ${resp.headers}[X-Content-Type-Options]    nosniff
    Should Be Equal    ${resp.headers}[X-Frame-Options]    DENY
    Dictionary Should Contain Key    ${resp.headers}    Content-Security-Policy
