*** Settings ***
Documentation     PB-03 / HU-03 — Auditoría y trazabilidad: quién, qué, cuándo, antes y después.
Resource          resources/common.resource
Suite Setup       Abrir Sesion API
Test Tags         PB-03    seguridad

*** Test Cases ***
Cambio de estado queda en la bitacora con antes y despues
    ${hs}=    Login Como    secretario1
    ${exp}=    Crear Expediente De Prueba    ${hs}
    ${hj}=    Login Como    juez1
    # RN-05.5 (Sprint 6): primero se admite la demanda; no se salta de radicado a audiencia
    ${admite}=    Create Dictionary    estado=en_tramite    motivo=Se admite la demanda
    POST On Session    api    /api/expedientes/${exp}[id]/estado    json=${admite}    headers=${hj}    expected_status=200
    ${body}=    Create Dictionary    estado=en_audiencia    motivo=Se fija audiencia
    POST On Session    api    /api/expedientes/${exp}[id]/estado    json=${body}    headers=${hj}
    ${ha}=    Login Como    admin1
    ${params}=    Create Dictionary    entidad=expediente    entidad_id=${exp}[id]
    ${resp}=    GET On Session    api    /api/auditoria    params=${params}    headers=${ha}
    ${ultimo}=    Set Variable    ${resp.json()}[0]
    Should Be Equal    ${ultimo}[accion]    CAMBIAR_ESTADO
    Should Be Equal    ${ultimo}[usuario]    juez1
    Should Contain    ${ultimo}[antes]    en_tramite
    Should Contain    ${ultimo}[despues]    en_audiencia

Login fallido tambien queda registrado
    # SEC-12 (Sprint 9): un usuario inexistente es anonimo: queda en accesos, fuera de la cadena
    ${body}=    Create Dictionary    username=intruso    password=x
    POST On Session    api    /api/auth/login    json=${body}    expected_status=401
    ${ha}=    Login Como    admin1
    ${resp}=    GET On Session    api    /api/auditoria/accesos    headers=${ha}
    ${usuarios}=    Evaluate    [r["usuario"] for r in $resp.json() if r["accion"] == "LOGIN_FALLIDO"]
    List Should Contain Value    ${usuarios}    intruso
    ${cadena}=    GET On Session    api    /api/auditoria    headers=${ha}
    ${encadenados}=    Evaluate    [r["usuario"] for r in $cadena.json()]
    List Should Not Contain Value    ${encadenados}    intruso

Las consultas del ciudadano no agregan registros a la cadena
    [Tags]    SEC-12
    ${hs}=    Login Como    secretario1
    ${exp}=    Crear Expediente De Prueba    ${hs}
    ${ha}=    Login Como    admin1
    ${antes}=    GET On Session    api    /api/auditoria/verificar    headers=${ha}
    ${body}=    Create Dictionary    numero=${exp}[numero]    codigo=${exp}[codigo_consulta]
    POST On Session    api    /api/publico/consulta    json=${body}    expected_status=200
    ${despues}=    GET On Session    api    /api/auditoria/verificar    headers=${ha}
    Should Be Equal As Integers    ${despues.json()}[registros]    ${antes.json()}[registros]
    Should Be True    ${despues.json()}[integra]
    ${acc}=    GET On Session    api    /api/auditoria/accesos    headers=${ha}
    ${refs}=    Evaluate    [r["referencia"] for r in $acc.json() if r["accion"] == "CONSULTA_PUBLICA"]
    List Should Contain Value    ${refs}    ${exp}[numero]

Solo el administrador ve los accesos anonimos
    [Tags]    SEC-12
    GET On Session    api    /api/auditoria/accesos    expected_status=401
    ${hj}=    Login Como    juez1
    GET On Session    api    /api/auditoria/accesos    headers=${hj}    expected_status=403

La cadena de hashes de la bitacora esta integra
    ${ha}=    Login Como    admin1
    ${resp}=    GET On Session    api    /api/auditoria/verificar    headers=${ha}
    Should Be True    ${resp.json()}[integra]
