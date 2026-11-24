"""SEC-01 y SEC-02 (Sprint 6): la configuración falla cerrado."""
import pytest

from app.config import DEMO_PASSWORD_PUBLICA, ConfiguracionInsegura, cargar

SECRETO = "x" * 64


def test_produccion_sin_jwt_secret_no_arranca():
    with pytest.raises(ConfiguracionInsegura):
        cargar({"APP_ENV": "produccion"})


def test_produccion_con_jwt_secret_corto_no_arranca():
    with pytest.raises(ConfiguracionInsegura):
        cargar({"APP_ENV": "produccion", "JWT_SECRET": "corto"})


def test_desarrollo_sin_secreto_genera_uno_aleatorio():
    with pytest.warns(UserWarning):
        a, b = cargar({}), cargar({})
    assert a.jwt_secret_generado and len(a.jwt_secret) == 64 and a.jwt_secret != b.jwt_secret


def test_seed_demo_apagado_por_defecto():
    assert cargar({"JWT_SECRET": SECRETO}).seed_demo is False


def test_produccion_con_seed_demo_exige_seed_password():
    with pytest.raises(ConfiguracionInsegura):
        cargar({"APP_ENV": "produccion", "JWT_SECRET": SECRETO, "SEED_DEMO": "1"})
    with pytest.raises(ConfiguracionInsegura):
        cargar({"APP_ENV": "produccion", "JWT_SECRET": SECRETO, "SEED_DEMO": "1",
                "SEED_PASSWORD": DEMO_PASSWORD_PUBLICA})


def test_produccion_valida_arranca():
    c = cargar({"APP_ENV": "produccion", "JWT_SECRET": SECRETO, "SEED_DEMO": "1", "SEED_PASSWORD": "Clave-Aleatoria-CI-9f3a",
                "AUDIT_KEY": "k" * 64})
    assert c.seed_demo and c.seed_password == "Clave-Aleatoria-CI-9f3a" and not c.jwt_secret_generado


def test_sec10_produccion_sin_audit_key_no_arranca():
    """SEC-10 (Sprint 7): la bitácora se firma con una clave que vive fuera de la BD."""
    with pytest.raises(ConfiguracionInsegura, match="AUDIT_KEY"):
        cargar({"APP_ENV": "produccion", "JWT_SECRET": SECRETO})
    with pytest.raises(ConfiguracionInsegura, match="AUDIT_KEY"):
        cargar({"APP_ENV": "produccion", "JWT_SECRET": SECRETO, "AUDIT_KEY": "corta"})
