#!/usr/bin/env python3
"""
Simple script to demonstrate and test rate limiting.

This script sends multiple rapid requests to test the rate limiting functionality.
"""

import asyncio
import aiohttp
import time
from typing import List, Dict, Any


async def send_request(session: aiohttp.ClientSession, url: str, request_num: int) -> Dict[str, Any]:
    """
    Send a single request and return response details.
    
    Args:
        session: HTTP session
        url: Endpoint URL
        request_num: Request number
        
    Returns:
        Dict with request details
    """
    start = time.time()
    try:
        async with session.get(url) as response:
            duration = time.time() - start
            
            return {
                "request_num": request_num,
                "status_code": response.status,
                "duration": duration,
                "rate_limit_limit": response.headers.get("X-RateLimit-Limit"),
                "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
                "rate_limit_reset": response.headers.get("X-RateLimit-Reset"),
            }
    except Exception as e:
        duration = time.time() - start
        return {
            "request_num": request_num,
            "status_code": "error",
            "duration": duration,
            "error": str(e),
        }


async def test_rate_limiting(
    base_url: str = "http://localhost:8080",
    num_requests: int = 10,
    delay: float = 0.1
):
    """
    Test rate limiting by sending multiple rapid requests.
    
    Args:
        base_url: Base URL of the API
        num_requests: Number of requests to send
        delay: Delay between requests in seconds
    """
    print(f"🧪 Testing Rate Limiting")
    print(f"Target: {base_url}/health")
    print(f"Requests: {num_requests}")
    print(f"Delay: {delay}s between requests")
    print("-" * 60)
    
    async with aiohttp.ClientSession() as session:
        results: List[Dict[str, Any]] = []
        
        for i in range(1, num_requests + 1):
            result = await send_request(session, f"{base_url}/health", i)
            results.append(result)
            
            # Print result
            if result["status_code"] == 200:
                print(
                    f"✅ Request {result['request_num']:3d}: "
                    f"Status={result['status_code']}, "
                    f"Duration={result['duration']:.3f}s, "
                    f"Remaining={result.get('rate_limit_remaining', 'N/A')}"
                )
            elif result["status_code"] == 429:
                print(
                    f"🚫 Request {result['request_num']:3d}: "
                    f"Status={result['status_code']} (Rate Limited!), "
                    f"Duration={result['duration']:.3f}s"
                )
            else:
                print(
                    f"❌ Request {result['request_num']:3d}: "
                    f"Status={result['status_code']}, "
                    f"Duration={result['duration']:.3f}s"
                )
            
            # Delay before next request
            if i < num_requests:
                await asyncio.sleep(delay)
        
        # Summary
        print("-" * 60)
        print("\n📊 Summary:")
        successful = sum(1 for r in results if r["status_code"] == 200)
        rate_limited = sum(1 for r in results if r["status_code"] == 429)
        errors = sum(1 for r in results if isinstance(r["status_code"], str))
        
        print(f"  ✅ Successful: {successful}")
        print(f"  🚫 Rate Limited: {rate_limited}")
        print(f"  ❌ Errors: {errors}")
        print(f"  📈 Total: {len(results)}")
        
        # Show rate limit headers from last successful request
        last_success = next((r for r in reversed(results) if r["status_code"] == 200), None)
        if last_success:
            print(f"\n⚙️  Rate Limit Configuration:")
            print(f"  Limit: {last_success.get('rate_limit_limit', 'N/A')} requests")
            print(f"  Window: {last_success.get('rate_limit_reset', 'N/A')} seconds")
            print(f"  Remaining: {last_success.get('rate_limit_remaining', 'N/A')} requests")


async def test_burst_requests(
    base_url: str = "http://localhost:8080",
    burst_size: int = 110
):
    """
    Test rate limiting with burst of requests (no delay).
    
    Args:
        base_url: Base URL of the API
        burst_size: Number of requests in burst
    """
    print(f"\n🚀 Testing Burst Rate Limiting (No Delay)")
    print(f"Target: {base_url}/health")
    print(f"Burst size: {burst_size} requests sent rapidly")
    print("-" * 60)
    
    async with aiohttp.ClientSession() as session:
        results = []
        
        # Send requests as fast as possible sequentially
        # This ensures they all hit the rate limit window
        for i in range(1, burst_size + 1):
            result = await send_request(session, f"{base_url}/health", i)
            results.append(result)
            
            # Show progress every 20 requests
            if i % 20 == 0 or result["status_code"] == 429:
                status_symbol = "✅" if result["status_code"] == 200 else "🚫"
                print(f"{status_symbol} Request {i}: Status={result['status_code']}, Remaining={result.get('rate_limit_remaining', 'N/A')}")
        
        # Summary
        successful = sum(1 for r in results if r["status_code"] == 200)
        rate_limited = sum(1 for r in results if r["status_code"] == 429)
        errors = sum(1 for r in results if isinstance(r["status_code"], str))
        
        print("-" * 60)
        print(f"\n📊 Burst Summary:")
        print(f"  ✅ Successful: {successful}")
        print(f"  🚫 Rate Limited: {rate_limited}")
        print(f"  ❌ Errors: {errors}")
        print(f"  📈 Total: {len(results)}")
        
        if rate_limited > 0:
            print(f"\n✅ Rate limiting is working! {rate_limited} requests were blocked.")
            print(f"   First rate-limited request: #{next(i for i, r in enumerate(results, 1) if r['status_code'] == 429)}")
        else:
            print(f"\n⚠️  No requests were rate limited. The limit might be higher than {burst_size}.")
            print(f"   Check configuration: RATE_LIMIT_REQUESTS and RATE_LIMIT_ENABLED")


async def main():
    """Main function to run rate limiting tests."""
    print("=" * 60)
    print("🔒 API Rate Limiting Test")
    print("=" * 60)
    print()
    
    # Test 1: Moderate paced requests (quick check)
    await test_rate_limiting(
        num_requests=5,
        delay=0.2
    )
    
    print("\n" + "=" * 60)
    
    # Wait for sliding window to reset
    print("\n⏳ Waiting 65 seconds for rate limit window to reset...")
    print("   (This ensures we start fresh for the burst test)\n")
    await asyncio.sleep(65)
    
    # Test 2: Burst of requests to trigger rate limiting
    await test_burst_requests(burst_size=110)
    
    print("\n" + "=" * 60)
    print("✅ Rate limiting tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")

