"""AraPulse: channels, read markers, messages, alerts, emergency pages and their targets

Revision ID: 0005_arapulse
Revises: 0004_org_profile_results
Create Date: 2026-10-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_arapulse'
down_revision: Union[str, Sequence[str], None] = '0004_org_profile_results'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('pulse_channels',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('facility_id', sa.String(length=36), sa.ForeignKey('facilities.id'), nullable=False),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('key', sa.String(length=90), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('department_id', sa.String(length=36), sa.ForeignKey('departments.id'), nullable=True),
        sa.Column('member_a', sa.String(length=36), nullable=True),
        sa.Column('member_b', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('facility_id', 'key'))
    op.create_index('ix_pulse_channels_facility_id', 'pulse_channels', ['facility_id'])

    op.create_table('pulse_reads',
        sa.Column('channel_id', sa.String(length=36), sa.ForeignKey('pulse_channels.id'), nullable=False),
        sa.Column('staff_id', sa.String(length=36), sa.ForeignKey('staff.id'), nullable=False),
        sa.Column('last_read_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('channel_id', 'staff_id'))
    op.create_index('ix_pulse_reads_staff_id', 'pulse_reads', ['staff_id'])

    op.create_table('pulse_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('facility_id', sa.String(length=36), nullable=False),
        sa.Column('channel_id', sa.String(length=36), sa.ForeignKey('pulse_channels.id'), nullable=False),
        sa.Column('sender_id', sa.String(length=36), nullable=True),
        sa.Column('kind', sa.String(length=15), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('priority', sa.String(length=10), nullable=False),
        sa.Column('patient_id', sa.String(length=36), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('ack_required', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('acknowledged_by', sa.String(length=36), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_pulse_messages_facility_id', 'pulse_messages', ['facility_id'])
    op.create_index('ix_pulse_messages_channel_created', 'pulse_messages', ['channel_id', 'created_at'])

    op.create_table('pulse_alerts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('facility_id', sa.String(length=36), nullable=False),
        sa.Column('recipient_id', sa.String(length=36), sa.ForeignKey('staff.id'), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('priority', sa.String(length=10), nullable=False),
        sa.Column('ack_required', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('patient_id', sa.String(length=36), nullable=True),
        sa.Column('visit_id', sa.String(length=36), nullable=True),
        sa.Column('ref_id', sa.String(length=36), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('seen_at', sa.DateTime(), nullable=True),
        sa.Column('acked_at', sa.DateTime(), nullable=True),
        sa.Column('acked_by', sa.String(length=36), nullable=True),
        sa.Column('escalated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_pulse_alerts_facility_id', 'pulse_alerts', ['facility_id'])
    op.create_index('ix_pulse_alerts_ref_id', 'pulse_alerts', ['ref_id'])
    op.create_index('ix_pulse_alerts_recipient_created', 'pulse_alerts', ['recipient_id', 'created_at'])

    op.create_table('pulse_pages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('facility_id', sa.String(length=36), sa.ForeignKey('facilities.id'), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=15), nullable=False),
        sa.Column('ward_id', sa.String(length=36), sa.ForeignKey('wards.id'), nullable=False),
        sa.Column('bed', sa.String(length=20), nullable=True),
        sa.Column('patient_id', sa.String(length=36), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('raised_by', sa.String(length=36), sa.ForeignKey('staff.id'), nullable=False),
        sa.Column('target_staff_id', sa.String(length=36), nullable=True),
        sa.Column('target_department_id', sa.String(length=36), nullable=True),
        sa.Column('channel_id', sa.String(length=36), nullable=True),
        sa.Column('responder_id', sa.String(length=36), nullable=True),
        sa.Column('eta_minutes', sa.Integer(), nullable=True),
        sa.Column('escalation_level', sa.Integer(), server_default='0', nullable=False),
        sa.Column('outcome', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('acked_at', sa.DateTime(), nullable=True),
        sa.Column('arrived_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('escalated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_pulse_pages_facility_status', 'pulse_pages', ['facility_id', 'status'])
    op.create_index('ix_pulse_pages_patient_id', 'pulse_pages', ['patient_id'])
    op.create_index('ix_pulse_pages_created_at', 'pulse_pages', ['created_at'])

    op.create_table('pulse_page_targets',
        sa.Column('page_id', sa.String(length=36), sa.ForeignKey('pulse_pages.id'), nullable=False),
        sa.Column('staff_id', sa.String(length=36), sa.ForeignKey('staff.id'), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('notified_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('page_id', 'staff_id'))
    op.create_index('ix_pulse_page_targets_staff_id', 'pulse_page_targets', ['staff_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_pulse_page_targets_staff_id', 'pulse_page_targets')
    op.drop_table('pulse_page_targets')
    for ix in ('ix_pulse_pages_created_at', 'ix_pulse_pages_patient_id', 'ix_pulse_pages_facility_status'):
        op.drop_index(ix, 'pulse_pages')
    op.drop_table('pulse_pages')
    for ix in ('ix_pulse_alerts_recipient_created', 'ix_pulse_alerts_ref_id', 'ix_pulse_alerts_facility_id'):
        op.drop_index(ix, 'pulse_alerts')
    op.drop_table('pulse_alerts')
    op.drop_index('ix_pulse_messages_channel_created', 'pulse_messages')
    op.drop_index('ix_pulse_messages_facility_id', 'pulse_messages')
    op.drop_table('pulse_messages')
    op.drop_index('ix_pulse_reads_staff_id', 'pulse_reads')
    op.drop_table('pulse_reads')
    op.drop_index('ix_pulse_channels_facility_id', 'pulse_channels')
    op.drop_table('pulse_channels')
