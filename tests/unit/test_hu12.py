"""HU-12 (Sprint 9): panel de congestión del administrador."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.models import EstadoExpediente as E
from app.routers.congestion import calcular

AHORA = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
HOY = AHORA.date()


def _exp(i, estado, juez_id, dias, limite=None):
    return SimpleNamespace(id=i, numero=f"EXP-2026-{i:06d}", materia="civil", estado=estado, juez_id=juez_id,
                           fecha_limite=limite, creado_en=AHORA - timedelta(days=dias))


# ---------- cálculo puro (sin base de datos) ----------

def test_hu12_dias_en_etapa_desde_el_ultimo_cambio_de_estado():
    exps = [_exp(1, E.en_tramite, 7, 50), _exp(2, E.en_tramite, 7, 10)]
    r = calcular(exps, {1: AHORA - timedelta(days=20)}, {7: "Juez A"}, HOY, AHORA)
    tramite = next(x for x in r["por_estado"] if x["estado"] == "en_tramite")
    assert tramite == {"estado": "en_tramite", "cantidad": 2, "dias_promedio_en_etapa": 15.0}  # (20 + 10) / 2
    assert r["antiguedad_promedio_dias"] == 30.0  # (50 + 10) / 2


def test_hu12_vencido_igual_que_las_alertas_pb06():
    exps = [
        _exp(1, E.en_audiencia, 7, 5, HOY - timedelta(days=1)),   # vencido
        _exp(2, E.con_sentencia, 7, 5, HOY - timedelta(days=9)),  # cerrado: no cuenta
        _exp(3, E.radicado, 7, 5, HOY),                           # vence hoy: aún no vencido
        _exp(4, E.radicado, 7, 5, None),                          # sin plazo
    ]
    r = calcular(exps, {}, {7: "Juez A"}, HOY, AHORA)
    assert r["vencidos"] == 1
    assert [m["vencido"] for m in r["mas_antiguos"] if m["id"] == 1] == [True]


def test_hu12_archivados_no_son_carga_activa():
    exps = [_exp(1, E.archivado, 7, 100), _exp(2, E.radicado, 7, 3)]
    r = calcular(exps, {}, {7: "Juez A"}, HOY, AHORA)
    assert r["total"] == 2 and r["activos"] == 1
    assert r["por_juez"] == [{"juez_id": 7, "juez": "Juez A", "activos": 1, "vencidos": 0,
                              "antiguedad_promedio_dias": 3.0}]
    assert [m["id"] for m in r["mas_antiguos"]] == [2]


def test_hu12_juez_con_vencidos_aparece_primero_y_sin_juez_se_agrupa():
    exps = [_exp(1, E.radicado, 7, 5), _exp(2, E.radicado, 7, 5), _exp(3, E.en_tramite, 8, 5, HOY - timedelta(days=3)),
            _exp(4, E.radicado, None, 2)]
    r = calcular(exps, {}, {7: "Juez A", 8: "Juez B"}, HOY, AHORA)
    assert [j["juez"] for j in r["por_juez"]] == ["Juez B", "Juez A", "Sin juez asignado"]


def test_hu12_cuello_de_botella_es_la_etapa_activa_mas_lenta():
    exps = [_exp(1, E.radicado, 7, 4), _exp(2, E.en_audiencia, 7, 60), _exp(3, E.archivado, 7, 400)]
    r = calcular(exps, {}, {7: "Juez A"}, HOY, AHORA)
    assert r["cuello_de_botella"] == "en_audiencia"  # el archivado no es un atasco
    assert calcular([], {}, {}, HOY, AHORA)["cuello_de_botella"] is None


def test_hu12_fechas_sin_zona_de_sqlite_y_maximo_cinco_antiguos():
    exps = [_exp(i, E.radicado, 7, i) for i in range(1, 8)]
    exps[0].creado_en = exps[0].creado_en.replace(tzinfo=None)  # así las devuelve SQLite
    r = calcular(exps, {}, {7: "Juez A"}, HOY, AHORA)
    assert [m["dias"] for m in r["mas_antiguos"]] == [7.0, 6.0, 5.0, 4.0, 3.0]


# ---------- API ----------

def test_hu12_solo_el_administrador_ve_el_panel(client, tokens):
    assert client.get("/api/congestion").status_code == 401
    for u in ("secretario1", "juez1", "abogado1"):
        assert client.get("/api/congestion", headers=tokens[u]).status_code == 403
    assert client.get("/api/congestion", headers=tokens["admin1"]).status_code == 200


def test_hu12_panel_cuadra_y_no_muestra_nombres_de_las_partes(client, tokens):
    r = client.get("/api/congestion", headers=tokens["admin1"]).json()
    assert sum(x["cantidad"] for x in r["por_estado"]) == r["total"]
    assert sum(j["activos"] for j in r["por_juez"]) == r["activos"]
    assert r["fecha"] == date.today().isoformat()
    texto = str(r)
    for parte in ("Comercial Istmo", "Juan Pérez", "María Rodríguez", "Ana Castillo", "Constructora Pacífico"):
        assert parte not in texto


def test_hu12_vencidos_coinciden_con_las_alertas(client, tokens):
    r = client.get("/api/congestion", headers=tokens["admin1"]).json()
    alertas = client.get("/api/expedientes/alertas", params={"dias": -1}, headers=tokens["admin1"]).json()
    assert r["vencidos"] == len(alertas)


def test_hu12_datos_demo_cuentan_la_historia(client, tokens):
    """El seed fecha la demo hacia atrás: el caso laboral lleva 90 días y está vencido."""
    r = client.get("/api/congestion", headers=tokens["admin1"]).json()
    demo = {m["numero"]: m for m in r["mas_antiguos"]}
    assert demo["EXP-2026-000003"]["vencido"] is True
    assert demo["EXP-2026-000003"]["dias"] >= 89
