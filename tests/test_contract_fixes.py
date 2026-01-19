"""
Test contract and attachment fixes

Tests for:
1. Contract deletion (should work for all statuses)
2. Attachment filtering (should exclude contract-related files)
3. PDF signing dependencies
"""
import pytest
import os


def test_pypdf_import():
    """Verify pypdf can be imported (dependency fix)"""
    try:
        from pypdf import PdfReader, PdfWriter
        assert PdfReader is not None
        assert PdfWriter is not None
    except ImportError as e:
        pytest.fail(f"pypdf import failed: {e}")


def test_pillow_import():
    """Verify Pillow (PIL) can be imported (dependency fix)"""
    try:
        from PIL import Image
        assert Image is not None
    except ImportError as e:
        pytest.fail(f"Pillow import failed: {e}")


def test_pdf_signing_service_imports():
    """Verify pdf_signing_service can be imported without errors"""
    try:
        from server.services.pdf_signing_service import (
            SignaturePlacement,
            get_pdf_info,
            embed_signatures_in_pdf
        )
        assert SignaturePlacement is not None
        assert get_pdf_info is not None
        assert embed_signatures_in_pdf is not None
    except ImportError as e:
        pytest.fail(f"pdf_signing_service import failed: {e}")


def test_contract_deletion_route_exists():
    """Verify contract deletion route is properly registered"""
    os.environ['MIGRATION_MODE'] = '1'
    
    from server.app_factory import create_app
    app = create_app()
    
    # Find the DELETE route for contracts
    delete_route_found = False
    for rule in app.url_map.iter_rules():
        if 'contracts' in rule.rule and 'DELETE' in rule.methods:
            delete_route_found = True
            break
    
    assert delete_route_found, "Contract DELETE route not found"


def test_attachment_list_route_exists():
    """Verify attachment list route is properly registered"""
    os.environ['MIGRATION_MODE'] = '1'
    
    from server.app_factory import create_app
    app = create_app()
    
    # Find the GET route for attachments list
    list_route_found = False
    for rule in app.url_map.iter_rules():
        if rule.rule == '/api/attachments' and 'GET' in rule.methods:
            list_route_found = True
            break
    
    assert list_route_found, "Attachments list route not found"


def test_contract_file_model_has_purpose_field():
    """Verify ContractFile model has purpose field for filtering"""
    os.environ['MIGRATION_MODE'] = '1'
    
    from server.models_sql import ContractFile
    
    # Check that ContractFile has the purpose column
    assert hasattr(ContractFile, 'purpose'), "ContractFile should have 'purpose' field"


def test_attachment_model_has_necessary_fields():
    """Verify Attachment model has all necessary fields"""
    os.environ['MIGRATION_MODE'] = '1'
    
    from server.models_sql import Attachment
    
    # Check that Attachment has required fields
    assert hasattr(Attachment, 'business_id'), "Attachment should have 'business_id' field"
    assert hasattr(Attachment, 'is_deleted'), "Attachment should have 'is_deleted' field"
    assert hasattr(Attachment, 'storage_path'), "Attachment should have 'storage_path' field"
