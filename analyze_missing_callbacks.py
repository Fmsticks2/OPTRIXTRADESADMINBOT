#!/usr/bin/env python3
"""
Script to analyze missing callback handlers in telegram_bot.py
"""

import re

def extract_callback_data_from_file(file_path):
    """Extract all callback_data values from the file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all callback_data="value" patterns
    callback_pattern = r'callback_data="([^"]+)"'
    callback_data_list = re.findall(callback_pattern, content)
    
    return set(callback_data_list)

def extract_handled_callbacks(file_path):
    """Extract all callback data handled in button_callback function"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the button_callback function
    button_callback_start = content.find('async def button_callback')
    if button_callback_start == -1:
        return set()
    
    # Find the end of the function (next async def or class)
    next_function = content.find('async def ', button_callback_start + 1)
    next_class = content.find('class ', button_callback_start + 1)
    
    end_pos = len(content)
    if next_function != -1:
        end_pos = min(end_pos, next_function)
    if next_class != -1:
        end_pos = min(end_pos, next_class)
    
    button_callback_content = content[button_callback_start:end_pos]
    
    # Extract handled callback data
    handled_callbacks = set()
    
    # Find if data == "value" patterns
    if_patterns = re.findall(r'if data == "([^"]+)"', button_callback_content)
    elif_patterns = re.findall(r'elif data == "([^"]+)"', button_callback_content)
    in_patterns = re.findall(r'data in \[([^\]]+)\]', button_callback_content)
    
    handled_callbacks.update(if_patterns)
    handled_callbacks.update(elif_patterns)
    
    # Handle the 'data in [...]' pattern
    for in_pattern in in_patterns:
        # Extract individual strings from the list
        list_items = re.findall(r'"([^"]+)"', in_pattern)
        handled_callbacks.update(list_items)
    
    return handled_callbacks

def main():
    file_path = 'telegram_bot.py'
    
    print("🔍 Analyzing callback data in telegram_bot.py...\n")
    
    # Extract all callback data defined in keyboards
    defined_callbacks = extract_callback_data_from_file(file_path)
    print(f"📋 Total callback_data defined in keyboards: {len(defined_callbacks)}")
    
    # Extract all callback data handled in button_callback
    handled_callbacks = extract_handled_callbacks(file_path)
    print(f"✅ Total callback_data handled in button_callback: {len(handled_callbacks)}")
    
    # Find missing handlers
    missing_handlers = defined_callbacks - handled_callbacks
    print(f"❌ Missing handlers: {len(missing_handlers)}\n")
    
    if missing_handlers:
        print("🚨 MISSING CALLBACK HANDLERS:")
        for callback in sorted(missing_handlers):
            print(f"  - {callback}")
        print()
    
    # Find handlers without definitions (potential dead code)
    unused_handlers = handled_callbacks - defined_callbacks
    if unused_handlers:
        print("⚠️  HANDLERS WITHOUT KEYBOARD DEFINITIONS:")
        for callback in sorted(unused_handlers):
            print(f"  - {callback}")
        print()
    
    # Show all defined callbacks for reference
    print("📝 ALL DEFINED CALLBACK DATA:")
    for callback in sorted(defined_callbacks):
        status = "✅" if callback in handled_callbacks else "❌"
        print(f"  {status} {callback}")
    
    print(f"\n📊 SUMMARY:")
    print(f"  • Defined: {len(defined_callbacks)}")
    print(f"  • Handled: {len(handled_callbacks)}")
    print(f"  • Missing: {len(missing_handlers)}")
    print(f"  • Unused: {len(unused_handlers)}")
    
    if missing_handlers:
        print(f"\n🔧 ACTION NEEDED: Add handlers for {len(missing_handlers)} missing callbacks")
        return False
    else:
        print(f"\n✅ ALL CALLBACKS PROPERLY HANDLED")
        return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)