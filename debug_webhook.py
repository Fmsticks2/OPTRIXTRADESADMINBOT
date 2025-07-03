#!/usr/bin/env python3
"""
Debug script to test webhook server locally and identify the exact error
"""

import asyncio
import logging
from webhook.webhook_server import WebhookServer
from telegram import Update
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_webhook_processing():
    """Test webhook processing locally to identify errors"""
    try:
        logger.info("🧪 Testing webhook processing locally...")
        
        # Create webhook server instance
        webhook_server = WebhookServer()
        
        # Initialize the server
        await webhook_server.startup()
        
        # Test update data
        test_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 123456789,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "chat": {
                    "id": 123456789,
                    "first_name": "Test",
                    "username": "testuser",
                    "type": "private"
                },
                "date": 1640995200,
                "text": "/start"
            }
        }
        
        logger.info(f"Testing with update: {json.dumps(test_update, indent=2)}")
        
        # Test processing the update
        await webhook_server.process_update(test_update)
        
        logger.info("✅ Webhook processing test completed successfully")
        
        # Cleanup
        await webhook_server.shutdown()
        
    except Exception as e:
        logger.error(f"❌ Error during webhook processing test: {e}", exc_info=True)
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_webhook_processing())