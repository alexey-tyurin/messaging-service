"""
Background worker for processing queued messages.
"""

import asyncio
import signal
import sys
from typing import Dict, Any, List
from datetime import datetime, timedelta

from app.db.session import db_manager
from app.db.redis import redis_manager
from app.services.message_service import MessageService
from app.services.webhook_service import WebhookProcessor
from app.core.observability import get_logger, MetricsCollector, monitor_performance
from app.core.config import settings


logger = get_logger(__name__)


class MessageProcessor:
    """Processes messages from the queue."""
    
    def __init__(self):
        """Initialize message processor."""
        self.running = False
        self.tasks: List[asyncio.Task] = []
    
    async def start(self):
        """Start the message processor."""
        logger.info("Starting message processor...")
        
        # Initialize database
        db_manager.init_db()
        await db_manager.create_tables()
        
        # Initialize Redis
        await redis_manager.init_redis()
        
        # Initialize providers
        from app.providers.base import ProviderFactory
        await ProviderFactory.init_providers()
        
        self.running = True
        
        # Start worker tasks
        self.tasks = [
            asyncio.create_task(self.process_sms_queue()),
            asyncio.create_task(self.process_mms_queue()),
            asyncio.create_task(self.process_email_queue()),
            asyncio.create_task(self.process_retry_queue()),
            asyncio.create_task(self.process_webhook_queue()),
            asyncio.create_task(self.update_metrics()),
        ]
        
        logger.info("Message processor started successfully")
        
        # Wait for all tasks
        await asyncio.gather(*self.tasks, return_exceptions=True)
    
    async def stop(self):
        """Stop the message processor."""
        logger.info("Stopping message processor...")
        
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Close connections
        await redis_manager.close()
        await db_manager.close()
        
        # Close providers
        from app.providers.base import ProviderFactory
        await ProviderFactory.close_providers()
        
        logger.info("Message processor stopped")
    
    @monitor_performance("process_sms_queue")
    async def process_sms_queue(self):
        """Process SMS/MMS message queue."""
        queue_name = "message_queue:sms"
        
        while self.running:
            try:
                # Get messages from queue
                messages = await redis_manager.dequeue_messages(
                    queue_name,
                    count=settings.queue_batch_size,
                    block=1000
                )
                
                if not messages:
                    await asyncio.sleep(1)
                    continue
                
                # Process messages
                for msg_data in messages:
                    await self._process_message(msg_data)
                
                # Update metrics
                queue_depth = await redis_manager.redis_client.xlen(queue_name)
                MetricsCollector.update_queue_depth(queue_name, queue_depth)
                
            except Exception as e:
                logger.error(f"Error processing SMS queue: {e}")
                await asyncio.sleep(5)
    
    @monitor_performance("process_mms_queue")
    async def process_mms_queue(self):
        """Process MMS message queue."""
        queue_name = "message_queue:mms"
        
        while self.running:
            try:
                # Get messages from queue
                messages = await redis_manager.dequeue_messages(
                    queue_name,
                    count=settings.queue_batch_size,
                    block=1000
                )
                
                if not messages:
                    await asyncio.sleep(1)
                    continue
                
                # Process messages
                for msg_data in messages:
                    await self._process_message(msg_data)
                
                # Update metrics
                queue_depth = await redis_manager.redis_client.xlen(queue_name)
                MetricsCollector.update_queue_depth(queue_name, queue_depth)
                
            except Exception as e:
                logger.error(f"Error processing MMS queue: {e}")
                await asyncio.sleep(5)
    
    @monitor_performance("process_email_queue")
    async def process_email_queue(self):
        """Process email message queue."""
        queue_name = "message_queue:email"
        
        while self.running:
            try:
                # Get messages from queue
                messages = await redis_manager.dequeue_messages(
                    queue_name,
                    count=settings.queue_batch_size,
                    block=1000
                )
                
                if not messages:
                    await asyncio.sleep(1)
                    continue
                
                # Process messages
                for msg_data in messages:
                    await self._process_message(msg_data)
                
                # Update metrics
                queue_depth = await redis_manager.redis_client.xlen(queue_name)
                MetricsCollector.update_queue_depth(queue_name, queue_depth)
                
            except Exception as e:
                logger.error(f"Error processing email queue: {e}")
                await asyncio.sleep(5)

    
    @monitor_performance("process_retry_queue")
    async def process_retry_queue(self):
        """Process messages scheduled for retry."""
        while self.running:
            try:
                # Check for messages ready for retry
                from app.models.database import Message, MessageStatus
                from sqlalchemy import select, and_
                
                async with db_manager.session_context() as db:
                    # Find messages ready for retry
                    now = datetime.utcnow()
                    query = select(Message).where(
                        and_(
                            Message.status == MessageStatus.RETRY,
                            Message.retry_after <= now
                        )
                    ).limit(10)
                    
                    result = await db.execute(query)
                    messages = result.scalars().all()
                    
                    for message in messages:
                        # Process retry
                        service = MessageService(db)
                        await service.process_outbound_message(str(message.id))
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error processing retry queue: {e}")
                await asyncio.sleep(30)
    
    async def process_webhook_queue(self):
        """Process webhook queue."""
        while self.running:
            try:
                async with db_manager.session_context() as db:
                    processor = WebhookProcessor(db)
                    
                    # Process one batch
                    webhooks = await redis_manager.dequeue_messages(
                        "webhook_queue",
                        count=10,
                        block=1000
                    )
                    
                    for webhook_data in webhooks:
                        try:
                            from app.services.webhook_service import WebhookService
                            service = WebhookService(db)
                            
                            await service.process_webhook(
                                webhook_data["provider"],
                                webhook_data["headers"],
                                webhook_data["body"]
                            )
                            
                        except Exception as e:
                            logger.error(f"Failed to process webhook: {e}")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in webhook processor: {e}")
                await asyncio.sleep(5)
    
    async def _process_message(self, msg_data: Dict[str, Any]):
        """Process a single message."""
        try:
            async with db_manager.session_context() as db:
                service = MessageService(db)
                
                message_id = msg_data.get("message_id")
                if not message_id:
                    logger.error("Message ID not found in queue data")
                    return
                
                # Process the message
                success = await service.process_outbound_message(message_id)
                
                if success:
                    logger.info(f"Successfully processed message: {message_id}")
                else:
                    logger.warning(f"Failed to process message: {message_id}")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}", msg_data=msg_data)
    
    async def update_metrics(self):
        """Update queue and system metrics."""
        while self.running:
            try:
                # Update queue depths
                for queue_type in ["sms", "mms", "email"]:
                    queue_name = f"message_queue:{queue_type}"
                    depth = await redis_manager.redis_client.xlen(queue_name)
                    MetricsCollector.update_queue_depth(queue_name, depth)
                
                # Update conversation counts
                from app.models.database import Conversation, ConversationStatus, MessageType
                from sqlalchemy import select, func, and_
                
                async with db_manager.session_context() as db:
                    for channel_type in MessageType:
                        query = select(func.count()).select_from(Conversation).where(
                            and_(
                                Conversation.channel_type == channel_type,
                                Conversation.status == ConversationStatus.ACTIVE
                            )
                        )
                        result = await db.execute(query)
                        count = result.scalar()
                        MetricsCollector.update_conversation_count(channel_type.value, count)
                
                # Update database pool metrics
                from app.core.observability import db_connection_pool
                if hasattr(db_manager.engine.pool, 'size'):
                    db_connection_pool.labels(metric_type="active").set(
                        db_manager.engine.pool.checkedout()
                    )
                    db_connection_pool.labels(metric_type="idle").set(
                        db_manager.engine.pool.size() - db_manager.engine.pool.checkedout()
                    )
                
                await asyncio.sleep(30)  # Update every 30 seconds
                
            except Exception as e:
                logger.error(f"Error updating metrics: {e}")
                await asyncio.sleep(60)


def signal_handler(processor: MessageProcessor):
    """Handle shutdown signals."""
    def handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(processor.stop())
        sys.exit(0)
    
    return handler


async def main():
    """Main entry point for the worker."""
    processor = MessageProcessor()
    
    # Set up signal handlers
    handler = signal_handler(processor)
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    
    try:
        await processor.start()
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        await processor.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
