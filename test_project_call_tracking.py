"""
Test project_id tracking in outbound calls
Verifies that calls initiated from projects are properly associated with project_id
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from server.routes_outbound import _validate_project_access


def test_validate_project_access_no_project():
    """Test that validation passes when no project_id is provided"""
    result = _validate_project_access(None, 1)
    assert result is True


@patch('server.routes_outbound.db')
def test_validate_project_access_valid_project(mock_db):
    """Test that validation passes for valid project"""
    mock_result = Mock()
    mock_result.scalar.return_value = 123  # Project exists
    mock_db.session.execute.return_value = mock_result
    
    result = _validate_project_access(123, 1)
    assert result is True


@patch('server.routes_outbound.db')
def test_validate_project_access_invalid_project(mock_db):
    """Test that validation fails for non-existent project"""
    mock_result = Mock()
    mock_result.scalar.return_value = None  # Project doesn't exist
    mock_db.session.execute.return_value = mock_result
    
    result = _validate_project_access(123, 1)
    assert result is False


@patch('server.routes_outbound.db')
def test_validate_project_access_wrong_tenant(mock_db):
    """Test that validation fails for project belonging to different tenant"""
    mock_result = Mock()
    mock_result.scalar.return_value = None  # Project doesn't belong to tenant
    mock_db.session.execute.return_value = mock_result
    
    result = _validate_project_access(123, 999)
    assert result is False


def test_models_have_project_id():
    """Test that CallLog and OutboundCallJob models have project_id field"""
    from server.models_sql import CallLog, OutboundCallJob
    
    # Check that models have project_id attribute
    assert hasattr(CallLog, 'project_id'), "CallLog should have project_id field"
    assert hasattr(OutboundCallJob, 'project_id'), "OutboundCallJob should have project_id field"


if __name__ == '__main__':
    # Run basic tests
    print("Testing project_id validation...")
    test_validate_project_access_no_project()
    print("✓ No project_id validation passed")
    
    print("\nTesting model attributes...")
    test_models_have_project_id()
    print("✓ Models have project_id field")
    
    print("\n✅ All basic tests passed!")
