"""Configuración leída de variables de entorno (12-factor).

En Kubernetes estas variables vienen de un ConfigMap / Secret (ver k8s/).

SEC-01 y SEC-02 (Sprint 6): la configuración falla cerrado.
- Sin JWT_SECRET propio la app NO arranca en producción (no hay valor por defecto público).
  En desarrollo se genera uno aleatorio en cada arranque para que la demo de un clic siga funcionando.
- Los datos demo solo se crean si se pide de forma explícita (SEED_DEMO=1).
  En producción, además, SEED_PASSWORD es obligatorio (no se usa la clave publicada).
"""
import os
import secrets
import warnings
from dataclasses import dataclass
from typing import Mapping

DEMO_PASSWORD_PUBLICA = "Demo-Judicial-2026"  # solo para desarrollo local (README, INICIAR_DEMO.bat)


class ConfiguracionInsegura(RuntimeError):
    """La app se niega a arrancar con una configuración insegura."""


@dataclass(frozen=True)
class Config:
    app_env: str
    database_url: str
    jwt_secret: str
    jwt_secret_generado: bool
    jwt_expire_minutes: int
    alerta_dias: int
    seed_demo: bool
    seed_password: str


def cargar(env: Mapping[str, str]) -> Config:
    app_env = env.get("APP_ENV", "desarrollo")
    produccion = app_env == "produccion"

    jwt_secret = env.get("JWT_SECRET", "")
    generado = False
    if not jwt_secret:
        if produccion:
            raise ConfiguracionInsegura("APP_ENV=produccion: falta JWT_SECRET (defínalo en el Secret).")
        jwt_secret, generado = secrets.token_hex(32), True
        warnings.warn("JWT_SECRET no definido: se generó uno aleatorio (solo desarrollo).", stacklevel=2)
    elif produccion and len(jwt_secret) < 32:
        raise ConfiguracionInsegura("APP_ENV=produccion: JWT_SECRET debe tener al menos 32 caracteres.")

    seed_demo = env.get("SEED_DEMO", "0") == "1"
    seed_password = env.get("SEED_PASSWORD", "")
    if seed_demo and not seed_password:
        if produccion:
            raise ConfiguracionInsegura("APP_ENV=produccion con SEED_DEMO=1 exige SEED_PASSWORD propio.")
        seed_password = DEMO_PASSWORD_PUBLICA
    if produccion and seed_password == DEMO_PASSWORD_PUBLICA:
        raise ConfiguracionInsegura("APP_ENV=produccion: SEED_PASSWORD no puede ser la clave demo publicada.")

    return Config(
        app_env=app_env,
        database_url=env.get("DATABASE_URL", "sqlite:///./expedientes.db"),
        jwt_secret=jwt_secret,
        jwt_secret_generado=generado,
        jwt_expire_minutes=int(env.get("JWT_EXPIRE_MINUTES", "60")),
        alerta_dias=int(env.get("ALERTA_DIAS", "5")),
        seed_demo=seed_demo,
        seed_password=seed_password,
    )


CONFIG = cargar(os.environ)

APP_ENV = CONFIG.app_env
DATABASE_URL = CONFIG.database_url
JWT_SECRET = CONFIG.jwt_secret
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = CONFIG.jwt_expire_minutes
# Días antes del vencimiento de un plazo para generar alerta (PB-06)
ALERTA_DIAS = CONFIG.alerta_dias
# Solo si es "1" se crean usuarios y expedientes de prueba al arrancar (SEC-02)
SEED_DEMO = CONFIG.seed_demo
SEED_PASSWORD = CONFIG.seed_password

# SEC-04: bloqueo temporal de cuentas y límite de fallos por IP
BLOQUEO_MINUTOS = int(os.getenv("BLOQUEO_MINUTOS", "15"))
LOGIN_MAX_FALLOS_IP = int(os.getenv("LOGIN_MAX_FALLOS_IP", "20"))
