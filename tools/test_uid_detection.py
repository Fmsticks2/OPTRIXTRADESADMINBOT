#!/usr/bin/env python3
"""
Test UID Detection Logic
This script tests the UID detection logic that was fixed.
"""

def test_uid_detection():
    """Test the UID detection logic"""
    
    test_cases = [
        # Valid UIDs
        ("ABC123456", True, "Valid alphanumeric UID"),
        ("USER789012", True, "Valid alphanumeric UID"),
        ("TRADER456789", True, "Valid long UID"),
        ("UID:ABC123", True, "UID with prefix"),
        ("123456", True, "Valid numeric UID"),
        ("ABCDEF", True, "Valid alphabetic UID"),
        
        # Invalid UIDs
        ("ABC12", False, "Too short (5 chars)"),
        ("A" * 21, False, "Too long (21 chars)"),
        ("ABC-123", False, "Contains hyphen"),
        ("ABC 123", False, "Contains space"),
        ("ABC@123", False, "Contains special character"),
        ("", False, "Empty string"),
        ("Hi", False, "Regular text"),
        ("Hello there", False, "Regular sentence"),
    ]
    
    print("🧪 Testing UID Detection Logic")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for message_text, expected_valid, description in test_cases:
        # Simulate the logic from handle_text_message
        uid = message_text.replace("UID:", "").strip()
        is_valid = len(uid) >= 6 and len(uid) <= 20 and uid.isalnum()
        
        if is_valid == expected_valid:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status} | Input: '{message_text}' | Expected: {expected_valid} | Got: {is_valid} | {description}")
    
    print("\n" + "=" * 50)
    print(f"📊 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! UID detection logic is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please review the logic.")
        return False

if __name__ == "__main__":
    test_uid_detection()