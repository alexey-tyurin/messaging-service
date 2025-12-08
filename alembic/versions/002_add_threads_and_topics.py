"""Add threads and topics

Revision ID: 002
Revises: 001
Create Date: 2025-12-08 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ConversationType enum
    conversation_type = sa.Enum('direct', 'topic', name='conversationtype')
    conversation_type.create(op.get_bind(), checkfirst=True)

    # Update conversations table
    op.add_column('conversations', sa.Column('type', conversation_type, server_default='direct', nullable=False))
    
    # Make participants nullable
    op.alter_column('conversations', 'participant_from', nullable=True)
    op.alter_column('conversations', 'participant_to', nullable=True)

    # Update messages table
    op.add_column('messages', sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_messages_parent_id', 'messages', 'messages', ['parent_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    # Downgrade messages
    op.drop_constraint('fk_messages_parent_id', 'messages', type_='foreignkey')
    op.drop_column('messages', 'parent_id')

    # Downgrade conversations
    # Note: This might fail if there are null participants, but correct for schema rollback
    op.alter_column('conversations', 'participant_from', nullable=False)
    op.alter_column('conversations', 'participant_to', nullable=False)
    
    op.drop_column('conversations', 'type')
    
    # Drop enum
    conversation_type = sa.Enum('direct', 'topic', name='conversationtype')
    conversation_type.drop(op.get_bind(), checkfirst=True)
