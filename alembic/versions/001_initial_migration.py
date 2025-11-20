"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables for messaging service."""
    
    # Create conversations table
    op.create_table('conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('participant_from', sa.String(length=255), nullable=False),
        sa.Column('participant_to', sa.String(length=255), nullable=False),
        sa.Column('channel_type', sa.Enum('sms', 'mms', 'email', name='messagetype'), nullable=False),
        sa.Column('status', sa.Enum('active', 'archived', 'closed', name='conversationstatus'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=True, default=0),
        sa.Column('unread_count', sa.Integer(), nullable=True, default=0),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('participant_from', 'participant_to', 'channel_type', name='uq_conversation_participants')
    )
    op.create_index('idx_conversation_participants', 'conversations', ['participant_from', 'participant_to', 'channel_type'])
    op.create_index('idx_conversation_updated', 'conversations', ['updated_at'])
    op.create_index('idx_conversation_last_message', 'conversations', ['last_message_at'])
    op.create_index(op.f('ix_conversations_channel_type'), 'conversations', ['channel_type'])
    op.create_index(op.f('ix_conversations_participant_from'), 'conversations', ['participant_from'])
    op.create_index(op.f('ix_conversations_participant_to'), 'conversations', ['participant_to'])
    op.create_index(op.f('ix_conversations_status'), 'conversations', ['status'])
    
    # Create messages table
    op.create_table('messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.Enum('twilio', 'sendgrid', 'internal', 'mock', name='provider'), nullable=False),
        sa.Column('provider_message_id', sa.String(length=255), nullable=True),
        sa.Column('direction', sa.Enum('inbound', 'outbound', name='messagedirection'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'queued', 'sending', 'sent', 'delivered', 'failed', 'retry', name='messagestatus'), nullable=False),
        sa.Column('message_type', sa.Enum('sms', 'mms', 'email', name='messagetype'), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('attachments', sa.JSON(), nullable=True),
        sa.Column('from_address', sa.String(length=255), nullable=False),
        sa.Column('to_address', sa.String(length=255), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=True, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=True, default=3),
        sa.Column('retry_after', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('headers', sa.JSON(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True, default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('retry_count >= 0', name='check_retry_count_positive'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_message_id', name='uq_provider_message')
    )
    op.create_index('idx_message_conversation_created', 'messages', ['conversation_id', 'created_at'])
    op.create_index('idx_message_status_created', 'messages', ['status', 'created_at'])
    op.create_index('idx_message_provider_status', 'messages', ['provider', 'status'])
    op.create_index('idx_message_direction_type', 'messages', ['direction', 'message_type'])
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'])
    op.create_index(op.f('ix_messages_direction'), 'messages', ['direction'])
    op.create_index(op.f('ix_messages_from_address'), 'messages', ['from_address'])
    op.create_index(op.f('ix_messages_message_type'), 'messages', ['message_type'])
    op.create_index(op.f('ix_messages_provider'), 'messages', ['provider'])
    op.create_index(op.f('ix_messages_provider_message_id'), 'messages', ['provider_message_id'])
    op.create_index(op.f('ix_messages_sent_at'), 'messages', ['sent_at'])
    op.create_index(op.f('ix_messages_status'), 'messages', ['status'])
    op.create_index(op.f('ix_messages_to_address'), 'messages', ['to_address'])
    
    # Create message_events table
    op.create_table('message_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.Enum('created', 'queued', 'sent', 'delivered', 'failed', 'retry', 'webhook_received', name='eventtype'), nullable=False),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('provider', sa.Enum('twilio', 'sendgrid', 'internal', 'mock', name='provider'), nullable=True),
        sa.Column('provider_event_id', sa.String(length=255), nullable=True),
        sa.Column('provider_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_event_message_created', 'message_events', ['message_id', 'created_at'])
    op.create_index('idx_event_type_created', 'message_events', ['event_type', 'created_at'])
    op.create_index('idx_event_provider', 'message_events', ['provider', 'provider_event_id'])
    op.create_index(op.f('ix_message_events_event_type'), 'message_events', ['event_type'])
    op.create_index(op.f('ix_message_events_message_id'), 'message_events', ['message_id'])
    
    # Create webhook_logs table
    op.create_table('webhook_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.Enum('twilio', 'sendgrid', 'internal', 'mock', name='provider'), nullable=False),
        sa.Column('webhook_id', sa.String(length=255), nullable=True),
        sa.Column('endpoint', sa.String(length=255), nullable=True),
        sa.Column('method', sa.String(length=10), nullable=True),
        sa.Column('headers', sa.JSON(), nullable=True),
        sa.Column('body', sa.JSON(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=True, default=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_webhook_provider_created', 'webhook_logs', ['provider', 'created_at'])
    op.create_index('idx_webhook_processed', 'webhook_logs', ['processed', 'created_at'])
    op.create_index(op.f('ix_webhook_logs_processed'), 'webhook_logs', ['processed'])
    op.create_index(op.f('ix_webhook_logs_provider'), 'webhook_logs', ['provider'])
    op.create_index(op.f('ix_webhook_logs_webhook_id'), 'webhook_logs', ['webhook_id'])
    
    # Create attachment_metadata table
    op.create_table('attachment_metadata',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=True),
        sa.Column('file_type', sa.String(length=100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_url', sa.Text(), nullable=True),
        sa.Column('storage_provider', sa.String(length=50), nullable=True),
        sa.Column('storage_key', sa.String(length=500), nullable=True),
        sa.Column('scanned', sa.Boolean(), nullable=True, default=False),
        sa.Column('scan_result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attachment_metadata_message_id'), 'attachment_metadata', ['message_id'])
    
    # Create rate_limits table
    op.create_table('rate_limits',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', sa.String(length=255), nullable=False),
        sa.Column('endpoint', sa.String(length=255), nullable=False),
        sa.Column('request_count', sa.Integer(), nullable=True, default=1),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id', 'endpoint', 'window_start', name='uq_rate_limit_window')
    )
    op.create_index('idx_rate_limit_client_endpoint', 'rate_limits', ['client_id', 'endpoint'])
    op.create_index('idx_rate_limit_window', 'rate_limits', ['window_end'])
    op.create_index(op.f('ix_rate_limits_client_id'), 'rate_limits', ['client_id'])
    op.create_index(op.f('ix_rate_limits_endpoint'), 'rate_limits', ['endpoint'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index(op.f('ix_rate_limits_endpoint'), table_name='rate_limits')
    op.drop_index(op.f('ix_rate_limits_client_id'), table_name='rate_limits')
    op.drop_index('idx_rate_limit_window', table_name='rate_limits')
    op.drop_index('idx_rate_limit_client_endpoint', table_name='rate_limits')
    op.drop_table('rate_limits')
    
    op.drop_index(op.f('ix_attachment_metadata_message_id'), table_name='attachment_metadata')
    op.drop_table('attachment_metadata')
    
    op.drop_index(op.f('ix_webhook_logs_webhook_id'), table_name='webhook_logs')
    op.drop_index(op.f('ix_webhook_logs_provider'), table_name='webhook_logs')
    op.drop_index(op.f('ix_webhook_logs_processed'), table_name='webhook_logs')
    op.drop_index('idx_webhook_processed', table_name='webhook_logs')
    op.drop_index('idx_webhook_provider_created', table_name='webhook_logs')
    op.drop_table('webhook_logs')
    
    op.drop_index(op.f('ix_message_events_message_id'), table_name='message_events')
    op.drop_index(op.f('ix_message_events_event_type'), table_name='message_events')
    op.drop_index('idx_event_provider', table_name='message_events')
    op.drop_index('idx_event_type_created', table_name='message_events')
    op.drop_index('idx_event_message_created', table_name='message_events')
    op.drop_table('message_events')
    
    op.drop_index(op.f('ix_messages_to_address'), table_name='messages')
    op.drop_index(op.f('ix_messages_status'), table_name='messages')
    op.drop_index(op.f('ix_messages_sent_at'), table_name='messages')
    op.drop_index(op.f('ix_messages_provider_message_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_provider'), table_name='messages')
    op.drop_index(op.f('ix_messages_message_type'), table_name='messages')
    op.drop_index(op.f('ix_messages_from_address'), table_name='messages')
    op.drop_index(op.f('ix_messages_direction'), table_name='messages')
    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_index('idx_message_direction_type', table_name='messages')
    op.drop_index('idx_message_provider_status', table_name='messages')
    op.drop_index('idx_message_status_created', table_name='messages')
    op.drop_index('idx_message_conversation_created', table_name='messages')
    op.drop_table('messages')
    
    op.drop_index(op.f('ix_conversations_status'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_participant_to'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_participant_from'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_channel_type'), table_name='conversations')
    op.drop_index('idx_conversation_last_message', table_name='conversations')
    op.drop_index('idx_conversation_updated', table_name='conversations')
    op.drop_index('idx_conversation_participants', table_name='conversations')
    op.drop_table('conversations')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS messagetype')
    op.execute('DROP TYPE IF EXISTS conversationstatus')
    op.execute('DROP TYPE IF EXISTS provider')
    op.execute('DROP TYPE IF EXISTS messagedirection')
    op.execute('DROP TYPE IF EXISTS messagestatus')
    op.execute('DROP TYPE IF EXISTS eventtype')
