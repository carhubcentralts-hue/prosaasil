#!/usr/bin/env python3
"""Test AI conversation import in Flask context"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

print("Testing AI conversation import...")

try:
    from ai_conversation_simple import HebrewAIConversation
    print("✅ Successfully imported HebrewAIConversation")
    
    conv = HebrewAIConversation()
    print("✅ Successfully created HebrewAIConversation instance")
    
    # Test a simple conversation
    result = conv.process_conversation_turn("test", "", 1)
    print(f"✅ Successfully processed conversation turn: {result['success']}")
    
except Exception as e:
    import traceback
    print(f"❌ Error: {e}")
    print(f"❌ Traceback: {traceback.format_exc()}")