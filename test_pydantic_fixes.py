#!/usr/bin/env python3
"""
Test script to verify Pydantic model fixes for strict schema compatibility
"""
import sys
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')

from pydantic import BaseModel, Field
from typing import Optional, List

# Import the fixed models
from server.agent_tools.tools_crm_context import (
    CreateLeadNoteInput,
    StructuredNoteData,
    UpdateLeadFieldsInput,
    LeadFieldsPatch
)

def test_structured_note_data():
    """Test StructuredNoteData model"""
    print("Testing StructuredNoteData...")
    
    # Create instance
    data = StructuredNoteData(
        sentiment="positive",
        outcome="scheduled_appointment",
        next_step_date="2024-01-20"
    )
    
    # Verify it can be converted to dict
    dict_data = data.model_dump()
    assert dict_data['sentiment'] == 'positive'
    assert dict_data['outcome'] == 'scheduled_appointment'
    
    # Test with None values
    data2 = StructuredNoteData()
    dict_data2 = data2.model_dump()
    assert dict_data2['sentiment'] is None
    
    print("✓ StructuredNoteData works correctly")

def test_create_lead_note_input():
    """Test CreateLeadNoteInput with new StructuredNoteData"""
    print("Testing CreateLeadNoteInput...")
    
    # Create with structured data
    input1 = CreateLeadNoteInput(
        business_id=1,
        lead_id=123,
        note_type="call_summary",
        content="Test note content",
        structured_data=StructuredNoteData(sentiment="positive")
    )
    
    # Verify structured_data can be converted to dict for database
    if input1.structured_data:
        db_data = input1.structured_data.model_dump()
        assert isinstance(db_data, dict)
        assert db_data['sentiment'] == 'positive'
    
    # Create without structured data
    input2 = CreateLeadNoteInput(
        business_id=1,
        lead_id=123,
        note_type="manual",
        content="Simple note"
    )
    assert input2.structured_data is None
    
    print("✓ CreateLeadNoteInput works correctly")

def test_lead_fields_patch():
    """Test LeadFieldsPatch model"""
    print("Testing LeadFieldsPatch...")
    
    # Create patch
    patch = LeadFieldsPatch(
        status="contacted",
        tags=["important", "follow-up"],
        city="Tel Aviv"
    )
    
    # Verify it can be converted to dict
    dict_patch = patch.model_dump()
    assert dict_patch['status'] == 'contacted'
    assert dict_patch['tags'] == ["important", "follow-up"]
    
    # Filter None values
    patch2 = LeadFieldsPatch(status="new")
    dict_patch2 = {k: v for k, v in patch2.model_dump().items() if v is not None}
    assert 'status' in dict_patch2
    assert 'tags' not in dict_patch2  # Should be filtered out
    
    print("✓ LeadFieldsPatch works correctly")

def test_update_lead_fields_input():
    """Test UpdateLeadFieldsInput with new LeadFieldsPatch"""
    print("Testing UpdateLeadFieldsInput...")
    
    # Create update input
    input1 = UpdateLeadFieldsInput(
        business_id=1,
        lead_id=456,
        patch=LeadFieldsPatch(
            status="qualified",
            summary="Good lead"
        )
    )
    
    # Verify patch can be converted to dict and filtered
    patch_dict = {k: v for k, v in input1.patch.model_dump().items() if v is not None}
    assert patch_dict['status'] == 'qualified'
    assert patch_dict['summary'] == 'Good lead'
    assert 'tags' not in patch_dict  # None values filtered
    
    print("✓ UpdateLeadFieldsInput works correctly")

def test_schema_generation():
    """Test that models generate proper JSON schemas without additionalProperties"""
    print("Testing schema generation...")
    
    # Get JSON schema
    schema1 = CreateLeadNoteInput.model_json_schema()
    
    # Check that structured_data has proper schema
    if '$defs' in schema1 and 'StructuredNoteData' in schema1['$defs']:
        struct_schema = schema1['$defs']['StructuredNoteData']
        # Should not have additionalProperties: true
        assert struct_schema.get('additionalProperties') != True, \
            "StructuredNoteData should not have additionalProperties: true"
        print(f"  StructuredNoteData schema: {struct_schema.get('type')}")
    
    schema2 = UpdateLeadFieldsInput.model_json_schema()
    
    # Check that patch has proper schema
    if '$defs' in schema2 and 'LeadFieldsPatch' in schema2['$defs']:
        patch_schema = schema2['$defs']['LeadFieldsPatch']
        # Should not have additionalProperties: true
        assert patch_schema.get('additionalProperties') != True, \
            "LeadFieldsPatch should not have additionalProperties: true"
        print(f"  LeadFieldsPatch schema: {patch_schema.get('type')}")
    
    print("✓ Schema generation is correct")

if __name__ == '__main__':
    print("=" * 60)
    print("Testing Pydantic model fixes for strict schema compatibility")
    print("=" * 60)
    
    try:
        test_structured_note_data()
        test_create_lead_note_input()
        test_lead_fields_patch()
        test_update_lead_fields_input()
        test_schema_generation()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
