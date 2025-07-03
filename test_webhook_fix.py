#!/usr/bin/env python3
"""
Test script to verify webhook server fixes
"""

import requests
import json
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebhookTester:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        
    def test_webhook_endpoint(self):
        """Test webhook endpoint with sample updates"""
        
        # Sample Telegram update (text message)
        sample_update = {
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
        
        test_cases = [
            ("Valid /start message", sample_update),
            ("Empty update", {}),
            ("Malformed update", {"invalid": "data"})
        ]
        
        for test_name, update_data in test_cases:
            try:
                logger.info(f"Testing: {test_name}")
                
                # Add proper headers that Telegram would send
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'TelegramBot (like TwitterBot)',
                    'X-Forwarded-For': '149.154.167.197',  # Telegram IP
                }
                
                response = requests.post(
                    self.webhook_url, 
                    json=update_data,
                    headers=headers,
                    timeout=10
                )
                
                logger.info(f"  Status: {response.status_code}")
                
                try:
                    response_data = response.json()
                    logger.info(f"  Response: {json.dumps(response_data, indent=2)[:200]}...")
                except:
                    logger.info(f"  Response: {response.text[:200]}...")
                
                if response.status_code == 500:
                    logger.error(f"❌ 500 error for {test_name}")
                elif response.status_code == 200:
                    logger.info(f"✅ Success for {test_name}")
                else:
                    logger.warning(f"⚠️  Unexpected status {response.status_code} for {test_name}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Request failed for {test_name}: {e}")
            except Exception as e:
                logger.error(f"❌ Unexpected error for {test_name}: {e}")
                
            # Small delay between tests
            time.sleep(0.5)
    
    def test_server_endpoints(self):
        """Test various server endpoints"""
        base_url = self.webhook_url.split('/webhook/')[0]
        
        endpoints = [
            ('Root', f"{base_url}/"),
            ('Health', f"{base_url}/health"),
            ('Webhook', self.webhook_url)
        ]
        
        server_running = False
        
        for name, url in endpoints:
            try:
                if name == 'Webhook':
                    # POST request for webhook with minimal data
                    headers = {
                        'Content-Type': 'application/json',
                        'User-Agent': 'TelegramBot (like TwitterBot)',
                    }
                    response = requests.post(url, json={"test": "ping"}, headers=headers, timeout=10)
                else:
                    # GET request for other endpoints
                    response = requests.get(url, timeout=10)
                
                logger.info(f"{name} endpoint status: {response.status_code}")
                
                if response.status_code == 200:
                    logger.info(f"✅ {name} endpoint responded")
                    if name != 'Webhook':  # Don't log webhook response as it might be an error
                        try:
                            data = response.json()
                            logger.info(f"  Response: {data}")
                        except:
                            logger.info(f"  Response: {response.text[:100]}...")
                    server_running = True
                elif response.status_code == 500 and name == 'Webhook':
                    logger.warning(f"⚠️  {name} endpoint returned 500")
                    server_running = True  # Server is running, just webhook has issues
                else:
                    logger.warning(f"⚠️  {name} endpoint returned {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ {name} endpoint failed: {e}")
                
        return server_running
    
    def test_webhook_with_debug_info(self):
        """Test webhook with additional debug information"""
        logger.info("\n🔍 Testing webhook with debug info...")
        
        # Test with a very simple update
        simple_update = {"update_id": 1}
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'TelegramBot (like TwitterBot)',
                'Accept': 'application/json',
            }
            
            logger.info(f"Sending to: {self.webhook_url}")
            logger.info(f"Headers: {headers}")
            logger.info(f"Data: {json.dumps(simple_update)}")
            
            response = requests.post(
                self.webhook_url,
                json=simple_update,
                headers=headers,
                timeout=15
            )
            
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            if response.text:
                logger.info(f"Response body: {response.text}")
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Debug test failed: {e}")
            return False

def main():
    """Main test function"""
    # Use the webhook URL from the previous setup
    webhook_url = "https://web-production-54a4.up.railway.app/webhook/7692303660:AAHkut6Cr2Dr_yXcuicg7FJ7BHmaEEOhN_0"
    
    logger.info("🧪 Testing Webhook Server Fixes")
    logger.info(f"Target URL: {webhook_url}")
    
    tester = WebhookTester(webhook_url)
    
    # Test server endpoints first
    logger.info("\n1. Testing Server Endpoints...")
    server_ok = tester.test_server_endpoints()
    
    if server_ok:
        logger.info("\n2. Testing Webhook with Debug Info...")
        debug_ok = tester.test_webhook_with_debug_info()
        
        if not debug_ok:
            logger.info("\n3. Testing Webhook Endpoint with Various Payloads...")
            tester.test_webhook_endpoint()
    else:
        logger.error("❌ Server not responding, skipping webhook tests")
    
    logger.info("\n🏁 Test completed")

if __name__ == "__main__":
    main()