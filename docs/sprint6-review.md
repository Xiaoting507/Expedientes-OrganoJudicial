# Sprint 6 · Review #2 — Cierre de calidad y seguridad del MVP

Equipo 1 (Neuronix) · Caso 1: Congestión Judicial · Sprint 6 (1 semana) · Factura NX-S6-001 (2026-11-07)

> Nota del Sprint 7: el código original del Sprint 6 (rama `sprint6`, commits `eeaa03f` y `16ec498`) no llegó al
> repositorio. El equipo del Sprint 7 lo rehízo sobre `ui-react` en los commits `8823824` y `1b5b7a2`, con las
> mismas pruebas (pytest 53/53, Robot 51/51).

## Incremento

| ID | Qué se corrigió | Dónde | Prueba |
| --- | --- | --- | --- |
| DEF-01 | Matriz de transiciones (RN-05.5): un archivado no se reabre; no hay sentencia sin admitir la demanda. 409 con estados permitidos | `app/models.py::TRANSICIONES`, `frontend/src/lib/formato.ts` | `test_def01_*` (4), Robot 02 |
| DEF-02 | Número EXP sin duplicados | `expedientes.py::_siguiente_numero` | `test_def02_*` |
| SEC-01 | Sin `JWT_SECRET` la app no arranca en producción | `app/config.py` | `test_config.py` |
| SEC-02 | `SEED_DEMO=0` por defecto; `SEED_PASSWORD` obligatorio en producción | `app/config.py`, `app/seed.py` | `test_config.py` |
| SEC-03 | Staging con clave demo aleatoria y Service ClusterIP | `ci-cd.yml`, `k8s/03-app.yaml` | pipeline |
| SEC-04 | Bloqueo de 15 min que expira, 429 por IP, desbloqueo por consola | `app/routers/auth.py`, `app/desbloquear.py` | `test_sec04_*` (3) |
| DEF-04 | Horas de la bitácora en hora de Panamá (antes +5 h) | `formato.ts::utc` | revisión manual |

## Horas y costo (estimado tarea por tarea)

| Rol | Persona | Horas | Tarifa | Importe |
| --- | --- | ---: | ---: | ---: |
| Product Owner | Leonardo Liang | 14 | 135 | 1,890 |
| Scrum Master | Jonathan Quinto | 18 | 115 | 2,070 |
| Backend | Javier Pravia | 32 | 128 | 4,096 |
| Frontend | Daniela Anaya | 18 | 95 | 1,710 |
| QA | Edwin Cisneros | 30 | 95 | 2,850 |
| **Total** | | **112** | | **12,616** |

Planeado 128 h; ejecutado 112 h (88 %). OpenVAS (16 h) quedó bloqueado por falta del contenedor de Greenbone.

## Presupuesto después del Sprint 6

1,000,000 − 650,000 (herramientas) − 72,752 (salarios S0–S6) = **277,248 neuronas**.

## Traspaso al Sprint 7

1. PR `sprint6` → `main` con el pipeline en verde.
2. OpenVAS (SEC-28).
3. Integridad de la bitácora: SEC-09, SEC-10, SEC-11.
4. Límite de tasa en la consulta pública (SEC-07) y 401 genérico (SEC-05).
5. HU-10: adjuntar PDF con hash.
6. Alembic (migraciones).
7. DEF-05 y DEF-03.

Arranque: `SETUP.md` y `INICIAR_DEMO.bat`. Pruebas: `pytest tests/unit` y `robot tests/robot`.
