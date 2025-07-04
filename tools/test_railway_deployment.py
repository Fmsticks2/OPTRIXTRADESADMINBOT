#!/usr/bin/env python3
"""
Test Railway deployment status and webhook connectivity
"""

import requests
import json
import sys
import time
from urllib.parse import urljoin

def test_railway_deployment():
    """Test Railway deployment endpoints"""
    
    # Railway URL from webhook setup
    base_url = "https://web-production-54a4.up.railway.app"
    
    print("🚀 Testing Railway Deployment")
    print("=" * 40)
    
    # Test endpoints
    endpoints = [
        "/",
        "/health", 
        "/debug",
        "/admin/webhook_info"
    ]
    
    for endpoint in endpoints:
        url = urljoin(base_url, endpoint)
        print(f"\n🔍 Testing: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"   Response: {json.dumps(data, indent=2)}")
                except:
                    print(f"   Response: {response.text[:200]}...")
            else:
                print(f"   Error: {response.text[:200]}...")
                
        except requests.exceptions.Timeout:
            print("   ❌ Timeout - Server not responding")
        except requests.exceptions.ConnectionError:
            print("   ❌ Connection Error - Server may be down")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Test webhook endpoint (should return 405 for GET)
    webhook_url = f"{base_url}/webhook/7692303660:AAHkut6Cr2Dr_yXcuicg7FJ7BHmaEEOhN_0"
    print(f"\n🔍 Testing webhook endpoint: {webhook_url}")
    
    try:
        response = requests.get(webhook_url, timeout=10)
        print(f"   Status: {response.status_code} (405 expected for GET)")
        if response.status_code == 405:
            print("   ✅ Webhook endpoint is accessible")
    except Exception as e:
        print(f"   ❌ Webhook test error: {e}")
    
    print("\n📊 Deployment Test Complete")

if __name__ == "__main__":
    test_railway_deployment()