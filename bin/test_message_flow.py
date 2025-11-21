#!/usr/bin/env python3
"""
Test script for complete message flow through Redis queues.

This script tests the 8-step message flow as described in QUICK_START.md:
1. Client sends message via REST API
2. Message validated and stored in PostgreSQL
3. Queued in Redis for async processing
4. Worker picks up message from queue
5. Provider selected based on message type
6. Message sent through provider API
7. Status updated and events recorded
8. Webhooks processed for delivery confirmations
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import httpx
import redis.asyncio as redis
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich import box

# Configuration
API_URL = "http://localhost:8080"
API_PREFIX = "/api/v1"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

console = Console()


class MessageFlowTester:
    """Tests complete message flow through the system."""
    
    def __init__(self):
        """Initialize tester."""
        self.http_client: Optional[httpx.AsyncClient] = None
        self.redis_client: Optional[redis.Redis] = None
        self.test_results: List[Dict[str, Any]] = []
        self.message_ids: List[str] = []
        
    async def setup(self):
        """Set up connections."""
        console.print("\n[bold cyan]Setting up connections...[/bold cyan]")
        
        # HTTP client
        self.http_client = httpx.AsyncClient(
            base_url=API_URL,
            timeout=30.0
        )
        
        # Redis client
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
        
        # Test connections
        try:
            # Test API
            response = await self.http_client.get("/health")
            if response.status_code == 200:
                console.print("✓ API connection successful", style="green")
            else:
                console.print(f"✗ API health check failed: {response.status_code}", style="red")
                return False
                
            # Test Redis
            await self.redis_client.ping()
            console.print("✓ Redis connection successful", style="green")
            
            return True
            
        except Exception as e:
            console.print(f"✗ Connection failed: {e}", style="red")
            return False
    
    async def cleanup(self):
        """Clean up connections."""
        if self.http_client:
            await self.http_client.aclose()
        if self.redis_client:
            await self.redis_client.close()
    
    async def test_complete_flow(self):
        """Test complete message flow for all message types."""
        console.print("\n[bold cyan]═══════════════════════════════════════════[/bold cyan]")
        console.print("[bold cyan]   Message Flow Integration Test Suite   [/bold cyan]")
        console.print("[bold cyan]═══════════════════════════════════════════[/bold cyan]\n")
        
        # Test messages
        test_messages = [
            {
                "name": "SMS Message",
                "data": {
                    "from": "+15551234567",
                    "to": "+15559876543",
                    "type": "sms",
                    "body": "Test SMS message - Testing complete flow through Redis queue"
                }
            },
            {
                "name": "MMS Message",
                "data": {
                    "from": "+15551234567",
                    "to": "+15559876543",
                    "type": "mms",
                    "body": "Test MMS message with attachment",
                    "attachments": ["https://example.com/test-image.jpg"]
                }
            },
            {
                "name": "Email Message",
                "data": {
                    "from": "sender@example.com",
                    "to": "recipient@example.com",
                    "type": "email",
                    "body": "<h1>Test Email</h1><p>Testing complete flow through Redis queue.</p>"
                }
            }
        ]
        
        for test_msg in test_messages:
            console.print(f"\n[bold yellow]Testing {test_msg['name']}...[/bold yellow]")
            console.print("─" * 60)
            
            result = await self.test_message_flow(
                test_msg["name"],
                test_msg["data"]
            )
            self.test_results.append(result)
            
            # Wait between tests
            await asyncio.sleep(2)
        
        # Test webhooks
        console.print("\n[bold yellow]Testing Webhook Flow...[/bold yellow]")
        console.print("─" * 60)
        await self.test_webhook_flow()
        
        # Display summary
        self.display_summary()
    
    async def test_message_flow(
        self,
        message_name: str,
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Test complete flow for a single message.
        
        Returns:
            Test result dictionary
        """
        result = {
            "name": message_name,
            "steps": {},
            "success": True,
            "message_id": None,
            "queue_name": None
        }
        
        # Step 1: Send message via REST API
        console.print("\n[cyan]Step 1: Sending message via REST API...[/cyan]")
        step1_result = await self._step1_send_message(message_data)
        result["steps"]["1_api_send"] = step1_result
        
        if not step1_result["success"]:
            result["success"] = False
            return result
            
        result["message_id"] = step1_result["message_id"]
        result["queue_name"] = f"message_queue:{message_data['type']}"
        
        # Step 2: Verify message in PostgreSQL
        console.print("\n[cyan]Step 2: Verifying message stored in PostgreSQL...[/cyan]")
        step2_result = await self._step2_verify_database(result["message_id"])
        result["steps"]["2_db_stored"] = step2_result
        
        if not step2_result["success"]:
            result["success"] = False
        
        # Step 3: Verify message queued in Redis
        console.print("\n[cyan]Step 3: Checking message queued in Redis...[/cyan]")
        step3_result = await self._step3_verify_queue(result["queue_name"])
        result["steps"]["3_redis_queued"] = step3_result
        
        if not step3_result["success"]:
            result["success"] = False
        
        # Step 4-7: Monitor worker processing
        console.print("\n[cyan]Steps 4-7: Monitoring worker processing...[/cyan]")
        step4_7_result = await self._step4_7_monitor_processing(
            result["message_id"],
            result["queue_name"]
        )
        result["steps"]["4_7_processing"] = step4_7_result
        
        if not step4_7_result["success"]:
            result["success"] = False
        
        # Step 8: Verify status and events
        console.print("\n[cyan]Step 8: Verifying status updates and events...[/cyan]")
        step8_result = await self._step8_verify_status(result["message_id"])
        result["steps"]["8_status_events"] = step8_result
        
        if not step8_result["success"]:
            result["success"] = False
        
        return result
    
    async def _step1_send_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Step 1: Send message via REST API."""
        try:
            response = await self.http_client.post(
                f"{API_PREFIX}/messages/send",
                json=message_data
            )
            
            if response.status_code == 201:
                data = response.json()
                console.print(f"  ✓ Message sent successfully", style="green")
                console.print(f"  Message ID: {data['id']}")
                console.print(f"  Status: {data['status']}")
                console.print(f"  Direction: {data['direction']}")
                
                return {
                    "success": True,
                    "message_id": data["id"],
                    "response": data
                }
            else:
                console.print(f"  ✗ Failed to send message: {response.status_code}", style="red")
                console.print(f"  Response: {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            console.print(f"  ✗ Error sending message: {e}", style="red")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _step2_verify_database(self, message_id: str) -> Dict[str, Any]:
        """Step 2: Verify message stored in PostgreSQL."""
        try:
            response = await self.http_client.get(
                f"{API_PREFIX}/messages/{message_id}"
            )
            
            if response.status_code == 200:
                data = response.json()
                console.print(f"  ✓ Message found in database", style="green")
                console.print(f"  From: {data['from_address']}")
                console.print(f"  To: {data['to_address']}")
                console.print(f"  Type: {data['message_type']}")
                console.print(f"  Created: {data['created_at']}")
                
                return {
                    "success": True,
                    "data": data
                }
            else:
                console.print(f"  ✗ Message not found in database", style="red")
                return {
                    "success": False,
                    "error": "Message not found"
                }
                
        except Exception as e:
            console.print(f"  ✗ Error querying database: {e}", style="red")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _step3_verify_queue(self, queue_name: str) -> Dict[str, Any]:
        """Step 3: Verify message queued in Redis."""
        try:
            # Check queue length
            queue_length = await self.redis_client.xlen(queue_name)
            
            console.print(f"  ✓ Queue '{queue_name}' exists", style="green")
            console.print(f"  Queue length: {queue_length}")
            
            # Try to peek at queue (without removing)
            if queue_length > 0:
                messages = await self.redis_client.xrange(queue_name, count=5)
                console.print(f"  Last message ID: {messages[-1][0] if messages else 'N/A'}")
            
            return {
                "success": True,
                "queue_length": queue_length,
                "queue_name": queue_name
            }
            
        except Exception as e:
            console.print(f"  ✗ Error checking Redis queue: {e}", style="red")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _step4_7_monitor_processing(
        self,
        message_id: str,
        queue_name: str
    ) -> Dict[str, Any]:
        """Steps 4-7: Monitor worker picking up and processing message."""
        try:
            console.print(f"  Monitoring for up to 30 seconds...")
            
            start_time = time.time()
            max_wait = 30
            check_interval = 1
            
            initial_queue_length = await self.redis_client.xlen(queue_name)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            ) as progress:
                task = progress.add_task(
                    "[cyan]Waiting for worker to process message...",
                    total=max_wait
                )
                
                while time.time() - start_time < max_wait:
                    # Check message status
                    response = await self.http_client.get(
                        f"{API_PREFIX}/messages/{message_id}"
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        status = data.get("status")
                        
                        # Check if processed
                        if status in ["sent", "delivered", "failed"]:
                            elapsed = time.time() - start_time
                            console.print(f"\n  ✓ Message processed!", style="green")
                            console.print(f"  Final status: {status}")
                            console.print(f"  Processing time: {elapsed:.2f}s")
                            console.print(f"  Provider: {data.get('provider', 'N/A')}")
                            
                            # Check queue
                            final_queue_length = await self.redis_client.xlen(queue_name)
                            console.print(f"  Queue length changed: {initial_queue_length} → {final_queue_length}")
                            
                            return {
                                "success": True,
                                "final_status": status,
                                "processing_time": elapsed,
                                "provider": data.get("provider")
                            }
                        
                        # Update progress
                        progress.update(
                            task,
                            advance=check_interval,
                            description=f"[cyan]Waiting for worker (status: {status})..."
                        )
                    
                    await asyncio.sleep(check_interval)
            
            # Timeout
            console.print(f"\n  ⚠ Worker processing timeout", style="yellow")
            console.print(f"  Note: Worker may still be processing or not running")
            
            return {
                "success": False,
                "error": "Processing timeout",
                "note": "Worker might not be running"
            }
            
        except Exception as e:
            console.print(f"  ✗ Error monitoring processing: {e}", style="red")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _step8_verify_status(self, message_id: str) -> Dict[str, Any]:
        """Step 8: Verify status updates and events recorded."""
        try:
            response = await self.http_client.get(
                f"{API_PREFIX}/messages/{message_id}"
            )
            
            if response.status_code == 200:
                data = response.json()
                
                console.print(f"  ✓ Status verified", style="green")
                console.print(f"  Current status: {data['status']}")
                console.print(f"  Created at: {data.get('created_at', 'N/A')}")
                console.print(f"  Sent at: {data.get('sent_at', 'N/A')}")
                console.print(f"  Delivered at: {data.get('delivered_at', 'N/A')}")
                
                # Check for events (if available)
                events = data.get("events", [])
                if events:
                    console.print(f"  Events recorded: {len(events)}")
                    for event in events[:3]:  # Show first 3
                        console.print(f"    - {event.get('event_type', 'unknown')}")
                
                return {
                    "success": True,
                    "status": data["status"],
                    "event_count": len(events)
                }
            else:
                console.print(f"  ✗ Failed to verify status", style="red")
                return {
                    "success": False,
                    "error": "Failed to get message"
                }
                
        except Exception as e:
            console.print(f"  ✗ Error verifying status: {e}", style="red")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def test_webhook_flow(self):
        """Test webhook processing flow."""
        # Test Twilio webhook
        console.print("\n[cyan]Testing Twilio webhook...[/cyan]")
        twilio_data = {
            "messaging_provider_id": f"test_twilio_{int(time.time())}",
            "from": "+15551234567",
            "to": "+15559876543",
            "type": "sms",
            "body": "Test inbound SMS via webhook",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        try:
            response = await self.http_client.post(
                f"{API_PREFIX}/webhooks/twilio",
                json=twilio_data
            )
            
            if response.status_code == 200:
                console.print(f"  ✓ Twilio webhook processed", style="green")
                console.print(f"  Response: {response.json()}")
            else:
                console.print(f"  ✗ Twilio webhook failed: {response.status_code}", style="red")
                
        except Exception as e:
            console.print(f"  ✗ Error testing webhook: {e}", style="red")
        
        # Test SendGrid webhook
        console.print("\n[cyan]Testing SendGrid webhook...[/cyan]")
        sendgrid_data = {
            "xillio_id": f"email_test_{int(time.time())}",
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "body": "<p>Test inbound email via webhook</p>",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        try:
            response = await self.http_client.post(
                f"{API_PREFIX}/webhooks/sendgrid",
                json=sendgrid_data
            )
            
            if response.status_code == 200:
                console.print(f"  ✓ SendGrid webhook processed", style="green")
                console.print(f"  Response: {response.json()}")
            else:
                console.print(f"  ✗ SendGrid webhook failed: {response.status_code}", style="red")
                
        except Exception as e:
            console.print(f"  ✗ Error testing webhook: {e}", style="red")
    
    def display_summary(self):
        """Display test summary."""
        console.print("\n[bold cyan]═══════════════════════════════════════════[/bold cyan]")
        console.print("[bold cyan]           Test Summary                   [/bold cyan]")
        console.print("[bold cyan]═══════════════════════════════════════════[/bold cyan]\n")
        
        # Create summary table
        table = Table(title="Message Flow Test Results", box=box.ROUNDED)
        table.add_column("Test", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Steps Passed", justify="center")
        table.add_column("Message ID", style="dim")
        
        for result in self.test_results:
            status_icon = "✓" if result["success"] else "✗"
            status_color = "green" if result["success"] else "red"
            
            steps_passed = sum(
                1 for step in result["steps"].values()
                if step.get("success", False)
            )
            total_steps = len(result["steps"])
            
            table.add_row(
                result["name"],
                f"[{status_color}]{status_icon}[/{status_color}]",
                f"{steps_passed}/{total_steps}",
                result["message_id"][:8] if result["message_id"] else "N/A"
            )
        
        console.print(table)
        
        # Overall result
        all_passed = all(r["success"] for r in self.test_results)
        if all_passed:
            console.print("\n[bold green]✓ All tests passed![/bold green]")
        else:
            console.print("\n[bold yellow]⚠ Some tests failed or timed out[/bold yellow]")
            console.print("\nCommon issues:")
            console.print("  • Worker not running: Start with 'make worker' or 'python -m app.workers.message_processor'")
            console.print("  • Database not initialized: Run 'make migrate'")
            console.print("  • Redis not running: Start with 'docker compose up -d redis'")
        
        console.print("\n[dim]Check logs for more details: logs/app.log[/dim]\n")


async def main():
    """Main entry point."""
    tester = MessageFlowTester()
    
    try:
        # Setup
        success = await tester.setup()
        if not success:
            console.print("\n[red]Failed to set up connections. Exiting.[/red]")
            sys.exit(1)
        
        # Run tests
        await tester.test_complete_flow()
        
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Test interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Test failed with error: {e}[/red]")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

