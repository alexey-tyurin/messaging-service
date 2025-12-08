"""remove unique constraint participants

Revision ID: 9d1eba11bc7a
Revises: d30531457b83
Create Date: 2025-12-08 16:25:58.667354

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d1eba11bc7a'
down_revision = 'd30531457b83'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('uq_conversation_participants', 'conversations', type_='unique')


def downgrade() -> None:
    op.create_unique_constraint('uq_conversation_participants', 'conversations', ['participant_from', 'participant_to', 'channel_type'])
