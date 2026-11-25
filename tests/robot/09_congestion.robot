*** Settings ***
Documentation     HU-12 (Sprint 9) — Panel de congestión: carga por juez, días por etapa y plazos vencidos.
...               Cada caso crea su propio juez y expediente, así no depende de los datos demo ni de otras suites.
Resource          resources/common.resource
Resource          resources/datos.resource
Suite Setup       Abrir Sesion API
Test Tags         HU-12    congestion

*** Keywords ***
Panel
    [Arguments]    ${headers}
    ${resp}=    GET On Session    api    /api/congestion    headers=${headers}    expected_status=200
    RETURN    ${resp.json()}

Fila Del Juez
    [Arguments]    ${panel}    ${juez_id}
    ${filas}=    Evaluate    [j for j in $panel["por_juez"] if j["juez_id"] == ${juez_id}]
    RETURN    ${filas}

*** Test Cases ***
Solo el administrador ve el panel de congestion
    GET On Session    api    /api/congestion    expected_status=401
    FOR    ${u}    IN    secretario1    juez1    abogado1
        ${h}=    Login Como    ${u}
        GET On Session    api    /api/congestion    headers=${h}    expected_status=403
    END

Un plazo vencido suma en el panel y en el despacho de su juez
    ${ha}=    Login Como    admin1
    ${hs}=    Login Como    secretario1
    ${juez}=    Crear Usuario Prueba    juez    ${ha}
    ${antes}=    Panel    ${ha}
    ${ayer}=    Fecha Relativa    -1
    Crear Expediente Propio    ${hs}    juez_id=${juez}[id]    fecha_limite=${ayer}
    ${despues}=    Panel    ${ha}
    Should Be Equal As Integers    ${despues}[vencidos]    ${${antes}[vencidos] + 1}
    Should Be Equal As Integers    ${despues}[activos]    ${${antes}[activos] + 1}
    ${fila}=    Fila Del Juez    ${despues}    ${juez}[id]
    Should Be Equal As Integers    ${fila}[0][activos]    1
    Should Be Equal As Integers    ${fila}[0][vencidos]    1

Archivar un expediente lo saca de la carga activa
    ${ha}=    Login Como    admin1
    ${hs}=    Login Como    secretario1
    ${juez}=    Crear Usuario Prueba    juez    ${ha}
    ${exp}=    Crear Expediente Propio    ${hs}    juez_id=${juez}[id]
    ${hj}=    Login Como    ${juez}[username]
    ${antes}=    Panel    ${ha}
    Cambiar Estado    ${hj}    ${exp}[id]    archivado
    ${despues}=    Panel    ${ha}
    Should Be Equal As Integers    ${despues}[activos]    ${${antes}[activos] - 1}
    Should Be Equal As Integers    ${despues}[total]    ${antes}[total]
    ${fila}=    Fila Del Juez    ${despues}    ${juez}[id]
    Should Be Empty    ${fila}

El panel cuadra y no muestra nombres de las partes
    ${ha}=    Login Como    admin1
    ${panel}=    Panel    ${ha}
    ${suma}=    Evaluate    sum(e["cantidad"] for e in $panel["por_estado"])
    Should Be Equal As Integers    ${suma}    ${panel}[total]
    ${texto}=    Convert To String    ${panel}
    Should Not Contain    ${texto}    QA Demandante
    Should Not Contain    ${texto}    QA Demandado
