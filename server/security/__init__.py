"""
Security module - RBAC and page-level permissions
"""
from .page_registry import PAGE_REGISTRY, get_all_page_keys, get_page_config

__all__ = ["PAGE_REGISTRY", "get_all_page_keys", "get_page_config"]
