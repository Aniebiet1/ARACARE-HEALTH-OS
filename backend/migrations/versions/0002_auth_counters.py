"""staff auth hardening and counters

Revision ID: 0002_auth_counters
Revises: 0001_baseline
Create Date: 2026-10-05 10:28:23.054285

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_auth_counters'
down_revision: Union[str, Sequence[str], None] = '0001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('counters',
    sa.Column('key', sa.String(length=60), nullable=False),
    sa.Column('value', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    with op.batch_alter_table('staff', schema=None) as batch_op:
        batch_op.add_column(sa.Column('token_version', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('failed_logins', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('locked_until', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('must_change_password', sa.Boolean(), server_default=sa.false(), nullable=False))

    # Patient numbers used to be COUNT(*)+1. Start each year's counter after the highest number already issued.
    # (Offline --sql mode can't read data; the app also skips numbers already taken, so that stays safe.)
    if context.is_offline_mode():
        return
    conn = op.get_bind()
    highest: dict[str, int] = {}
    for (number,) in conn.execute(sa.text("SELECT patient_number FROM patients")):
        prefix, _, seq = number.rpartition("-")
        if seq.isdigit():
            highest[prefix + "-"] = max(highest.get(prefix + "-", 0), int(seq))
    counters = sa.table('counters', sa.column('key', sa.String), sa.column('value', sa.Integer))
    if highest:
        op.bulk_insert(counters, [{"key": f"patient_number:{k}", "value": v} for k, v in highest.items()])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('staff', schema=None) as batch_op:
        batch_op.drop_column('must_change_password')
        batch_op.drop_column('locked_until')
        batch_op.drop_column('failed_logins')
        batch_op.drop_column('token_version')

    op.drop_table('counters')
