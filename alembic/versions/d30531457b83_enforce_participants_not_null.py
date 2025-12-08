"""enforce participants not null

Revision ID: d30531457b83
Revises: 002
Create Date: 2025-12-08 16:19:11.338190

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd30531457b83'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove conversations with null participants to allow setting NOT NULL
    op.execute("DELETE FROM conversations WHERE participant_from IS NULL OR participant_to IS NULL")
    op.alter_column('conversations', 'participant_from', nullable=False)
    op.alter_column('conversations', 'participant_to', nullable=False)


def downgrade() -> None:
    op.alter_column('conversations', 'participant_from', nullable=True)
    op.alter_column('conversations', 'participant_to', nullable=True)
