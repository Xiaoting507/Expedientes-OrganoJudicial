# Sprint 7 — HU-10, bitácora firmada y nuevo equipo

Equipo 1 (Neuronix) · Caso 1: Congestión Judicial · Sprint 7 (1 semana, 09/11 al 15/11/2026) · Factura NX-S7-001 (2026-11-16)

| Rol | Sprints 0 a 6 | Sprint 7 |
| --- | --- | --- |
| Product Owner | Leonardo Liang | Leonardo Liang |
| Scrum Master | Jonathan Quinto | Juan Vasquez |
| Backend | Javier Pravia | Daniel Pimentel |
| Frontend | Daniela Anaya | Jimmy Aizprua |
| QA | Edwin Cisneros | Cecc |

## Objetivo

Completar el producto con HU-10 (adjuntar PDF con huella SHA-256) y cerrar los hallazgos de integridad de la
bitácora, con un equipo nuevo que recibe el proyecto del Sprint 6.

## Incremento

| ID | Qué se hizo | Dónde | Prueba |
| --- | --- | --- | --- |
| Imprevisto | El código del Sprint 6 no estaba en el repositorio: se rehízo (rama `sprint6`) | `8823824`, `1b5b7a2`, `765cc5b` | pytest 53/53, Robot 51/51 |
| HU-10 | PDF del expediente: solo PDF real, máx. 10 MB, huella SHA-256 verificada al descargar (409 si cambió) | `app/routers/documentos.py`, `frontend/src/components/documentos.tsx` | `test_hu10_*` (9), Robot 08 (5) |
| SEC-09/10 | Bitácora v2: HMAC-SHA256 con `AUDIT_KEY` fuera de la BD; cubre `expediente_id` e `ip` | `app/audit.py` | `test_sec09_*`, `test_sec10_*` |
| SEC-11 | Escrituras de la bitácora serializadas (sin bifurcaciones) | `app/audit.py` | `test_sec11_*` (12 hilos) |
| SEC-05 | Login sin enumeración de usuarios | `app/routers/auth.py` | `test_sec05_*` |
| SEC-07 | 429 tras 10 consultas públicas fallidas por IP | `app/routers/publico.py` | `test_sec07_*` |
| DEF-03 | 422 si `plazo_desde > plazo_hasta` | `expedientes.py::listar` | `test_def03_*` |
| DEF-05 | El abogado solo presenta escritos y no en expedientes cerrados | `expedientes.py::agregar_actuacion` | `test_def05_*`, Robot 05 |
| Alembic | Migración `0001`; en producción el esquema se aplica con `alembic upgrade head` | `migrations/`, `app/migraciones.py` | `test_alembic_*` |
| SEC-16/17/18 | Sin `/docs` en producción, `Cache-Control: no-store`, sin cabecera `server` | `app/main.py`, `Dockerfile` | `test_respuestas_*` |

Commits del sprint: `198aac7`, `f8d2a11`, `554c11b`, `9195b81`.

## Calidad

- pytest: 73/73 (Sprint 6: 53). Cobertura de `app/`: 95 % (866 sentencias).
- Robot Framework: 57/57 (Sprint 6: 51). Nueva suite `08_documentos` y caso DEF-05.
- Rendimiento (200 peticiones, p50/p95 ms): bandeja 9.8/12.5 · detalle 23.5/29.7 · consulta 17.7/21.4 ·
  descarga de PDF de 200 KB 23.9/28.1 · subida 21.8/25.5 · login 257/300 (PBKDF2 a propósito).
- Confiabilidad: 1,105 peticiones, 0 respuestas 5xx; la bitácora verificó 715 registros íntegros.
- Mantenibilidad: complejidad promedio A (2.44), índice de mantenibilidad A en los 18 archivos (promedio 69.6).
- Defectos: DEF-03 y DEF-05 cerrados; 0 abiertos.

## Seguridad

- Cerrados en el sprint: SEC-05, SEC-06, SEC-07, SEC-09, SEC-10, SEC-11, SEC-13, SEC-16 y SEC-18.
- Parciales: SEC-17 y SEC-22 (`pip-audit` ya corre en el pipeline: 0 vulnerabilidades).
- Sin cerrar: 15 de 28 (Sprint 6: 23). Altos: 0.
- Pendiente: OpenVAS (SEC-28). La máquina del equipo no tiene Docker corriendo ni el feed de Greenbone.

## Horas y costo (estimado tarea por tarea)

| Rol | Persona | Horas | Tarifa | Importe |
| --- | --- | ---: | ---: | ---: |
| Product Owner | Leonardo Liang | 14 | 135 | 1,890 |
| Scrum Master | Juan Vasquez | 17 | 115 | 1,955 |
| Backend | Daniel Pimentel | 46 | 128 | 5,888 |
| Frontend | Jimmy Aizprua | 20 | 95 | 1,900 |
| QA | Cecc | 30 | 95 | 2,850 |
| **Total** | | **127** | | **14,483** |

Plan: 129 h. Trabajado: 127 h = 109 h del plan + 18 h imprevistas (rehacer el Sprint 6 y recuperar el repositorio).
No se hizo: OpenVAS (16 h) y la encuesta SUS (4 h).

## Presupuesto

1,000,000 − 650,000 (herramientas) − 87,235 (salarios S0–S7) − 4,530 (entrega final) − 20,000 (imprevistos)
= **238,235 neuronas** (≈ 47,647 por integrante; ≈ 51,647 si no se usan los imprevistos).

## Pendiente para la entrega final

1. PR `sprint7` → `main` con el pipeline en verde.
2. OpenVAS en una máquina con Docker.
3. Encuesta SUS con usuarios reales.
4. Hallazgos Medios restantes: SEC-08 (código en la URL), SEC-12 (eventos anónimos en la bitácora), SEC-14 (TLS).
5. En producción, los PDF necesitan un volumen compartido entre réplicas (PVC ReadWriteMany).
