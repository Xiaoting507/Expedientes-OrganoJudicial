"""SEC-12 (Sprint 9): tabla eventos_acceso para eventos anónimos fuera de la cadena

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('eventos_acceso',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('fecha', sa.DateTime(timezone=True), nullable=False),
    sa.Column('accion', sa.String(length=60), nullable=False),
    sa.Column('usuario', sa.String(length=60), nullable=False),
    sa.Column('referencia', sa.String(length=40), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('eventos_acceso', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_eventos_acceso_fecha'), ['fecha'], unique=False)
        batch_op.create_index(batch_op.f('ix_eventos_acceso_accion'), ['accion'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('eventos_acceso', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_eventos_acceso_accion'))
        batch_op.drop_index(batch_op.f('ix_eventos_acceso_fecha'))
    op.drop_table('eventos_acceso')
