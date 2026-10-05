"""facility branding for patient receipts

Revision ID: 0003_facility_branding
Revises: 0002_auth_counters
Create Date: 2026-10-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_facility_branding'
down_revision: Union[str, Sequence[str], None] = '0002_auth_counters'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('facilities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('address', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('motto', sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column('logo_path', sa.String(length=300), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('facilities', schema=None) as batch_op:
        batch_op.drop_column('logo_path')
        batch_op.drop_column('motto')
        batch_op.drop_column('email')
        batch_op.drop_column('phone')
        batch_op.drop_column('address')
