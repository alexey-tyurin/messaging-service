#!/usr/bin/env python3
"""
Simple demonstration script for Redis caching on get_message and get_conversation endpoints.

This script demonstrates that:
1. First call fetches from database and caches in Redis
2. Second call retrieves from Redis cache
3. Updates invalidate the cache

Run this after starting the service and having some test data.
"""

import asyncio
import httpx
import time

BASE_URL = "http://localhost:8080"


async def demo_message_caching():
    """Demonstrate message caching."""
    print("\n" + "="*70)
    print("MESSAGE CACHING DEMONSTRATION")
    print("="*70)
    
    async with httpx.AsyncClient() as client:
        # First, send a message to create test data
        print("\n1. Creating a test message...")
        send_response = await client.post(
            f"{BASE_URL}/api/v1/messages/send",
            json={
                "from": "+15551234567",
                "to": "+15559876543",
                "type": "sms",
                "body": "Test message for cache demo"
            }
        )
        
        if send_response.status_code != 201:
            print(f"   ❌ Failed to create message: {send_response.status_code}")
            print(f"   Response: {send_response.text}")
            return
        
        message_data = send_response.json()
        message_id = message_data["id"]
        print(f"   ✅ Message created: {message_id}")
        
        # Wait a moment for async processing
        await asyncio.sleep(1)
        
        # First GET - should be a cache miss
        print(f"\n2. First GET request (cache MISS - fetches from DB)...")
        start = time.time()
        first_response = await client.get(f"{BASE_URL}/api/v1/messages/{message_id}")
        first_duration = (time.time() - start) * 1000
        
        if first_response.status_code == 200:
            print(f"   ✅ Message retrieved: {first_response.json()['body']}")
            print(f"   ⏱️  Duration: {first_duration:.2f}ms")
        else:
            print(f"   ❌ Failed: {first_response.status_code}")
        
        # Second GET - should be a cache hit
        print(f"\n3. Second GET request (cache HIT - retrieves from Redis)...")
        start = time.time()
        second_response = await client.get(f"{BASE_URL}/api/v1/messages/{message_id}")
        second_duration = (time.time() - start) * 1000
        
        if second_response.status_code == 200:
            print(f"   ✅ Message retrieved from cache: {second_response.json()['body']}")
            print(f"   ⏱️  Duration: {second_duration:.2f}ms")
            print(f"   🚀 Speedup: {(first_duration/second_duration):.2f}x faster")
        else:
            print(f"   ❌ Failed: {second_response.status_code}")
        
        # Update message status - should invalidate cache
        print(f"\n4. Updating message status (invalidates cache)...")
        update_response = await client.patch(
            f"{BASE_URL}/api/v1/messages/{message_id}/status",
            json={"status": "delivered", "metadata": {"test": "cache_invalidation"}}
        )
        
        if update_response.status_code == 200:
            print(f"   ✅ Message status updated")
        else:
            print(f"   ❌ Failed: {update_response.status_code}")
        
        # Third GET - should be a cache miss again (cache was invalidated)
        print(f"\n5. Third GET request (cache MISS - cache was invalidated)...")
        start = time.time()
        third_response = await client.get(f"{BASE_URL}/api/v1/messages/{message_id}")
        third_duration = (time.time() - start) * 1000
        
        if third_response.status_code == 200:
            print(f"   ✅ Message retrieved: {third_response.json()['status']}")
            print(f"   ⏱️  Duration: {third_duration:.2f}ms")
        else:
            print(f"   ❌ Failed: {third_response.status_code}")


async def demo_conversation_caching():
    """Demonstrate conversation caching."""
    print("\n" + "="*70)
    print("CONVERSATION CACHING DEMONSTRATION")
    print("="*70)
    
    async with httpx.AsyncClient() as client:
        # First, send a message to create a conversation
        print("\n1. Creating a test conversation...")
        send_response = await client.post(
            f"{BASE_URL}/api/v1/messages/send",
            json={
                "from": "+15557777777",
                "to": "+15558888888",
                "type": "sms",
                "body": "Test conversation for cache demo"
            }
        )
        
        if send_response.status_code != 201:
            print(f"   ❌ Failed to create message: {send_response.status_code}")
            return
        
        message_data = send_response.json()
        conversation_id = message_data["conversation_id"]
        print(f"   ✅ Conversation created: {conversation_id}")
        
        # Wait a moment
        await asyncio.sleep(1)
        
        # First GET - should be a cache miss
        print(f"\n2. First GET request (cache MISS - fetches from DB)...")
        start = time.time()
        first_response = await client.get(f"{BASE_URL}/api/v1/conversations/{conversation_id}")
        first_duration = (time.time() - start) * 1000
        
        if first_response.status_code == 200:
            data = first_response.json()
            print(f"   ✅ Conversation retrieved: {data['participant_from']} -> {data['participant_to']}")
            print(f"   ⏱️  Duration: {first_duration:.2f}ms")
        else:
            print(f"   ❌ Failed: {first_response.status_code}")
        
        # Second GET - should be a cache hit
        print(f"\n3. Second GET request (cache HIT - retrieves from Redis)...")
        start = time.time()
        second_response = await client.get(f"{BASE_URL}/api/v1/conversations/{conversation_id}")
        second_duration = (time.time() - start) * 1000
        
        if second_response.status_code == 200:
            data = second_response.json()
            print(f"   ✅ Conversation retrieved from cache")
            print(f"   ⏱️  Duration: {second_duration:.2f}ms")
            print(f"   🚀 Speedup: {(first_duration/second_duration):.2f}x faster")
        else:
            print(f"   ❌ Failed: {second_response.status_code}")
        
        # Mark as read - should invalidate cache
        print(f"\n4. Marking conversation as read (invalidates cache)...")
        mark_response = await client.post(
            f"{BASE_URL}/api/v1/conversations/{conversation_id}/mark-read"
        )
        
        if mark_response.status_code == 204:
            print(f"   ✅ Conversation marked as read")
        else:
            print(f"   ❌ Failed: {mark_response.status_code}")
        
        # Third GET - should be a cache miss again
        print(f"\n5. Third GET request (cache MISS - cache was invalidated)...")
        start = time.time()
        third_response = await client.get(f"{BASE_URL}/api/v1/conversations/{conversation_id}")
        third_duration = (time.time() - start) * 1000
        
        if third_response.status_code == 200:
            data = third_response.json()
            print(f"   ✅ Conversation retrieved: unread_count={data['unread_count']}")
            print(f"   ⏱️  Duration: {third_duration:.2f}ms")
        else:
            print(f"   ❌ Failed: {third_response.status_code}")


async def check_service_health():
    """Check if the service is running."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                return True
    except Exception:
        pass
    return False


async def main():
    """Run the demonstration."""
    print("\n" + "="*70)
    print("REDIS CACHING DEMONSTRATION")
    print("="*70)
    
    print("\nChecking if service is running...")
    if not await check_service_health():
        print("❌ Service is not running at", BASE_URL)
        print("\nPlease start the service first:")
        print("  make run")
        print("\nOr:")
        print("  docker compose up")
        return
    
    print("✅ Service is running")
    
    # Run demonstrations
    await demo_message_caching()
    await demo_conversation_caching()
    
    print("\n" + "="*70)
    print("DEMONSTRATION COMPLETE")
    print("="*70)
    print("\n📊 Summary:")
    print("  • First GET requests fetch from database and cache in Redis")
    print("  • Second GET requests retrieve from Redis cache (faster)")
    print("  • Updates invalidate the cache automatically")
    print("  • Cache TTL is 5 minutes (300 seconds)")
    print("\n💡 Check application logs for cache hit/miss debug messages")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

