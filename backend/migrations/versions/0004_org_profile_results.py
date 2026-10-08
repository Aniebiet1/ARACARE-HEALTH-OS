"""hospital profile + onboarding, departments, wards, staff position/department/duty, lab results, dispensing

Revision ID: 0004_org_profile_results
Revises: 0003_facility_branding
Create Date: 2026-10-06 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_org_profile_results'
down_revision: Union[str, Sequence[str], None] = '0003_facility_branding'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('facilities', schema=None) as b:
        b.add_column(sa.Column('facility_type', sa.String(length=30), nullable=True))
        b.add_column(sa.Column('ownership', sa.String(length=20), nullable=True))
        b.add_column(sa.Column('license_number', sa.String(length=60), nullable=True))
        b.add_column(sa.Column('city', sa.String(length=80), nullable=True))
        b.add_column(sa.Column('lga', sa.String(length=80), nullable=True))
        b.add_column(sa.Column('emergency_phone', sa.String(length=60), nullable=True))
        b.add_column(sa.Column('website', sa.String(length=160), nullable=True))
        b.add_column(sa.Column('bed_capacity', sa.Integer(), nullable=True))
        b.add_column(sa.Column('open_24h', sa.Boolean(), server_default=sa.true(), nullable=False))
        b.add_column(sa.Column('onboarded_at', sa.DateTime(), nullable=True))
        b.add_column(sa.Column('onboarded_by', sa.String(length=36), nullable=True))

    op.create_table('departments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('facility_id', sa.String(length=36), sa.ForeignKey('facilities.id'), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('kind', sa.String(length=15), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('facility_id', 'code'))
    op.create_index('ix_departments_facility_id', 'departments', ['facility_id'])

    op.create_table('wards',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('facility_id', sa.String(length=36), sa.ForeignKey('facilities.id'), nullable=False),
        sa.Column('department_id', sa.String(length=36), sa.ForeignKey('departments.id'), nullable=True),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('floor', sa.String(length=40), nullable=True),
        sa.Column('bed_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('facility_id', 'code'))
    op.create_index('ix_wards_facility_id', 'wards', ['facility_id'])

    with op.batch_alter_table('staff', schema=None) as b:
        b.add_column(sa.Column('position', sa.String(length=80), nullable=True))
        b.add_column(sa.Column('department_id', sa.String(length=36), nullable=True))
        b.add_column(sa.Column('phone', sa.String(length=30), nullable=True))
        b.add_column(sa.Column('on_duty', sa.Boolean(), server_default=sa.true(), nullable=False))
        b.create_index('ix_staff_department_id', ['department_id'])
        b.create_foreign_key('fk_staff_department', 'departments', ['department_id'], ['id'])

    with op.batch_alter_table('lab_orders', schema=None) as b:
        b.add_column(sa.Column('started_at', sa.DateTime(), nullable=True))
        b.add_column(sa.Column('result_text', sa.Text(), nullable=True))
        b.add_column(sa.Column('result_flag', sa.String(length=10), nullable=True))
        b.add_column(sa.Column('resulted_by', sa.String(length=36), nullable=True))
        b.add_column(sa.Column('resulted_at', sa.DateTime(), nullable=True))

    with op.batch_alter_table('medication_orders', schema=None) as b:
        b.add_column(sa.Column('dispensed_by', sa.String(length=36), nullable=True))
        b.add_column(sa.Column('dispensed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('medication_orders', schema=None) as b:
        b.drop_column('dispensed_at')
        b.drop_column('dispensed_by')
    with op.batch_alter_table('lab_orders', schema=None) as b:
        for c in ('resulted_at', 'resulted_by', 'result_flag', 'result_text', 'started_at'):
            b.drop_column(c)
    with op.batch_alter_table('staff', schema=None) as b:
        b.drop_constraint('fk_staff_department', type_='foreignkey')
        b.drop_index('ix_staff_department_id')
        for c in ('on_duty', 'phone', 'department_id', 'position'):
            b.drop_column(c)
    op.drop_index('ix_wards_facility_id', 'wards')
    op.drop_table('wards')
    op.drop_index('ix_departments_facility_id', 'departments')
    op.drop_table('departments')
    with op.batch_alter_table('facilities', schema=None) as b:
        for c in ('onboarded_by', 'onboarded_at', 'open_24h', 'bed_capacity', 'website', 'emergency_phone',
                  'lga', 'city', 'license_number', 'ownership', 'facility_type'):
            b.drop_column(c)
