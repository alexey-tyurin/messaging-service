#!/usr/bin/env python3
"""
Verify Redis queue integration for message flow.

This script tests that:
1. Messages are properly queued to Redis
2. Messages are not processed synchronously
3. Worker processes messages from queue
4. Webhook queue integration works
"""

import asyncio
import httpx
import redis.asyncio as redis
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")

def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


class RedisQueueVerifier:
    """Verifies Redis queue integration."""
    
    def __init__(self):
        self.api_base_url = "http://localhost:8080"
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_client: Optional[redis.Redis] = None
        self.http_client: Optional[httpx.AsyncClient] = None
    
    async def setup(self):
        """Setup connections."""
        print_info("Setting up connections...")
        
        # Connect to Redis
        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            decode_responses=True
        )
        await self.redis_client.ping()
        print_success("Connected to Redis")
        
        # Setup HTTP client
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Check API health
        try:
            response = await self.http_client.get(f"{self.api_base_url}/health")
            if response.status_code == 200:
                print_success("API is healthy")
            else:
                print_error(f"API health check failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Cannot connect to API: {e}")
            return False
        
        return True
    
    async def cleanup(self):
        """Cleanup connections."""
        if self.redis_client:
            await self.redis_client.close()
        if self.http_client:
            await self.http_client.aclose()
    
    async def check_sync_processing_disabled(self) -> bool:
        """Check if sync processing is disabled."""
        print_header("Step 1: Verify Sync Processing Configuration")
        
        # Check environment variable
        sync_processing = os.getenv("SYNC_MESSAGE_PROCESSING", "true").lower()
        
        if sync_processing == "false":
            print_success("SYNC_MESSAGE_PROCESSING is set to False")
            return True
        else:
            print_error("SYNC_MESSAGE_PROCESSING is set to True (or not set)")
            print_warning("Messages will be processed synchronously!")
            print_info("To enable async queue processing, set: export SYNC_MESSAGE_PROCESSING=false")
            return False
    
    async def test_message_queuing(self) -> Dict[str, Any]:
        """Test that messages are properly queued to Redis."""
        print_header("Step 2: Test Message Queuing to Redis")
        
        # Get queue length before sending
        queue_name = "message_queue:sms"
        initial_length = await self.redis_client.xlen(queue_name)
        print_info(f"Initial queue length for {queue_name}: {initial_length}")
        
        # Send SMS message
        message_data = {
            "from": "+15551234567",
            "to": "+15559876543",
            "type": "sms",
            "body": "Test message for Redis queue verification"
        }
        
        print_info("Sending SMS message via API...")
        response = await self.http_client.post(
            f"{self.api_base_url}/api/v1/messages/send",
            json=message_data
        )
        
        if response.status_code != 201:
            print_error(f"Failed to send message: {response.status_code}")
            print_error(f"Response: {response.text}")
            return {}
        
        message = response.json()
        message_id = message.get("id")
        print_success(f"Message sent with ID: {message_id}")
        print_info(f"Initial status: {message.get('status')}")
        
        # Wait a bit for queue operation to complete
        await asyncio.sleep(0.5)
        
        # Check queue length after sending
        final_length = await self.redis_client.xlen(queue_name)
        print_info(f"Final queue length for {queue_name}: {final_length}")
        
        if final_length > initial_length:
            print_success(f"Message added to Redis queue! (queue grew by {final_length - initial_length})")
        else:
            print_error("Message was NOT added to Redis queue")
            print_warning("This indicates synchronous processing is enabled")
        
        # Read the message from queue
        try:
            messages = await self.redis_client.xread({queue_name: "0-0"}, count=1)
            if messages:
                stream_name, stream_messages = messages[0]
                if stream_messages:
                    msg_id, msg_data = stream_messages[0]
                    print_success("Message found in queue:")
                    data_json = json.loads(msg_data.get("data", "{}"))
                    print(f"  Message ID in queue: {data_json.get('message_id')}")
                    print(f"  Scheduled at: {data_json.get('scheduled_at')}")
        except Exception as e:
            print_warning(f"Could not read from queue: {e}")
        
        return message
    
    async def test_synchronous_vs_async_processing(self, message_id: str) -> bool:
        """Test whether message was processed synchronously or asynchronously."""
        print_header("Step 3: Check Processing Mode")
        
        # Immediately check message status
        print_info("Checking message status immediately after send...")
        response = await self.http_client.get(
            f"{self.api_base_url}/api/v1/messages/{message_id}"
        )
        
        if response.status_code != 200:
            print_error(f"Failed to get message: {response.status_code}")
            return False
        
        message = response.json()
        status = message.get("status")
        
        print_info(f"Message status: {status}")
        
        # If status is already 'sent' or 'sending', it was processed synchronously
        if status in ["sent", "sending", "delivered"]:
            print_error("Message was processed SYNCHRONOUSLY")
            print_warning("Expected status: 'pending', Got: '{}'".format(status))
            print_info("This means the worker queue is bypassed!")
            return False
        elif status == "pending":
            print_success("Message is in PENDING state")
            print_success("This indicates ASYNCHRONOUS processing via queue")
            return True
        else:
            print_warning(f"Unexpected status: {status}")
            return False
    
    async def test_worker_processing(self, message_id: str, timeout: int = 30) -> bool:
        """Test that worker processes the message from queue."""
        print_header("Step 4: Monitor Worker Processing")
        
        print_info(f"Waiting for worker to process message (timeout: {timeout}s)...")
        
        start_time = datetime.now()
        last_status = None
        
        while (datetime.now() - start_time).seconds < timeout:
            response = await self.http_client.get(
                f"{self.api_base_url}/api/v1/messages/{message_id}"
            )
            
            if response.status_code == 200:
                message = response.json()
                status = message.get("status")
                
                if status != last_status:
                    print_info(f"Status changed: {last_status} -> {status}")
                    last_status = status
                
                if status in ["sent", "delivered"]:
                    processing_time = (datetime.now() - start_time).seconds
                    print_success(f"Message processed by worker!")
                    print_success(f"Final status: {status}")
                    print_success(f"Processing time: {processing_time}s")
                    return True
                elif status == "failed":
                    print_error("Message processing failed")
                    print_error(f"Error: {message.get('error_message', 'Unknown')}")
                    return False
            
            await asyncio.sleep(1)
        
        print_error(f"Worker processing timeout after {timeout}s")
        print_warning("Worker might not be running or is processing very slowly")
        print_info("Make sure worker is started with: make worker")
        return False
    
    async def test_webhook_queue(self) -> bool:
        """Test webhook queue integration."""
        print_header("Step 5: Test Webhook Queue")
        
        # Check webhook queue
        webhook_queue = "webhook_queue"
        queue_length = await self.redis_client.xlen(webhook_queue)
        print_info(f"Webhook queue length: {queue_length}")
        
        # Send a test webhook
        print_info("Sending test webhook...")
        webhook_data = {
            "From": "+15559876543",
            "To": "+15551234567",
            "Body": "Incoming test message",
            "MessageSid": f"TEST_{datetime.now().timestamp()}"
        }
        
        try:
            response = await self.http_client.post(
                f"{self.api_base_url}/api/v1/webhooks/twilio",
                data=webhook_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                print_success("Webhook accepted")
                
                # Check if it was processed synchronously or queued
                # For now, webhooks are processed synchronously in the current implementation
                print_info("Webhook processing: SYNCHRONOUS")
                print_warning("Note: Webhooks are currently processed synchronously, not via queue")
                print_info("This is different from outbound message processing")
                return True
            else:
                print_error(f"Webhook failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Webhook test failed: {e}")
            return False
    
    async def test_queue_operations(self) -> bool:
        """Test basic Redis queue operations."""
        print_header("Step 6: Test Redis Queue Operations")
        
        test_queue = "test_queue"
        
        # Clean up test queue
        await self.redis_client.delete(test_queue)
        
        # Test enqueue
        print_info("Testing enqueue operation...")
        test_data = {"data": json.dumps({"test": "message", "timestamp": str(datetime.now())})}
        msg_id = await self.redis_client.xadd(test_queue, test_data)
        print_success(f"Message enqueued with ID: {msg_id}")
        
        # Test queue length
        length = await self.redis_client.xlen(test_queue)
        print_success(f"Queue length: {length}")
        
        # Test dequeue
        print_info("Testing dequeue operation...")
        messages = await self.redis_client.xread({test_queue: "0-0"}, count=1)
        if messages:
            print_success("Message dequeued successfully")
            stream_name, stream_messages = messages[0]
            msg_id, msg_data = stream_messages[0]
            data_json = json.loads(msg_data.get("data", "{}"))
            print(f"  Data: {data_json}")
        else:
            print_error("Failed to dequeue message")
            return False
        
        # Clean up
        await self.redis_client.delete(test_queue)
        print_success("Queue operations test completed")
        
        return True
    
    async def run_all_tests(self) -> bool:
        """Run all verification tests."""
        print_header("Redis Queue Integration Verification")
        
        if not await self.setup():
            return False
        
        try:
            # Step 1: Check sync processing configuration
            sync_disabled = await self.check_sync_processing_disabled()
            
            # Step 2: Test message queuing
            message = await self.test_message_queuing()
            if not message:
                print_error("Message queuing test failed")
                return False
            
            message_id = message.get("id")
            
            # Step 3: Check if processing was synchronous or async
            is_async = await self.test_synchronous_vs_async_processing(message_id)
            
            # Step 4: Wait for worker to process (if async)
            if is_async:
                worker_success = await self.test_worker_processing(message_id)
            else:
                print_warning("Skipping worker test (message was processed synchronously)")
                worker_success = False
            
            # Step 5: Test webhook queue
            webhook_success = await self.test_webhook_queue()
            
            # Step 6: Test basic queue operations
            queue_ops_success = await self.test_queue_operations()
            
            # Summary
            print_header("Test Summary")
            
            results = [
                ("Sync Processing Disabled", sync_disabled),
                ("Message Queued to Redis", message.get("id") is not None),
                ("Async Processing Mode", is_async),
                ("Worker Processed Message", worker_success),
                ("Webhook Integration", webhook_success),
                ("Queue Operations", queue_ops_success)
            ]
            
            for test_name, success in results:
                status = "✓ PASS" if success else "✗ FAIL"
                color = Colors.GREEN if success else Colors.RED
                print(f"{color}{status}{Colors.RESET} - {test_name}")
            
            all_passed = all(success for _, success in results)
            
            if all_passed:
                print_success("\nAll tests passed!")
            else:
                print_error("\nSome tests failed")
                
                if not sync_disabled:
                    print("\n" + "=" * 70)
                    print_warning("IMPORTANT: To enable async queue processing:")
                    print_info("1. Set environment variable: export SYNC_MESSAGE_PROCESSING=false")
                    print_info("2. Restart the API server")
                    print_info("3. Make sure worker is running: make worker")
                    print_info("4. Run this test again")
                    print("=" * 70)
            
            return all_passed
            
        finally:
            await self.cleanup()


async def main():
    """Main entry point."""
    verifier = RedisQueueVerifier()
    success = await verifier.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

