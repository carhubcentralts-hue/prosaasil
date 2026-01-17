"""
Page Registry - Single Source of Truth for all pages/modules in ProSaaS
Every page must be registered here to appear in the system
הנחיית-על: מרשם דפים מרכזי לכל המערכת
"""
from typing import Dict, List, Optional, Literal

# Role types
RoleType = Literal["agent", "manager", "admin", "owner", "system_admin"]

class PageConfig:
    """Configuration for a single page/module"""
    def __init__(
        self,
        page_key: str,
        title_he: str,
        route: str,
        min_role: RoleType = "agent",
        category: str = "general",
        api_tags: Optional[List[str]] = None,
        icon: Optional[str] = None,
        description: Optional[str] = None,
        is_system_admin_only: bool = False
    ):
        self.page_key = page_key
        self.title_he = title_he
        self.route = route
        self.min_role = min_role
        self.category = category
        self.api_tags = api_tags or []
        self.icon = icon
        self.description = description
        self.is_system_admin_only = is_system_admin_only
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "page_key": self.page_key,
            "title_he": self.title_he,
            "route": self.route,
            "min_role": self.min_role,
            "category": self.category,
            "api_tags": self.api_tags,
            "icon": self.icon,
            "description": self.description,
            "is_system_admin_only": self.is_system_admin_only
        }

# מרשם דפים מרכזי - כל דף חדש חייב להירשם כאן
PAGE_REGISTRY: Dict[str, PageConfig] = {
    # Dashboard
    "dashboard": PageConfig(
        page_key="dashboard",
        title_he="סקירה כללית",
        route="/app/business/overview",
        min_role="agent",
        category="dashboard",
        api_tags=["overview", "statistics"],
        icon="LayoutDashboard",
        description="מסך סקירה כללית עם KPIs"
    ),
    
    # CRM
    "crm_leads": PageConfig(
        page_key="crm_leads",
        title_he="לידים",
        route="/app/leads",
        min_role="agent",
        category="crm",
        api_tags=["leads", "crm"],
        icon="Users",
        description="ניהול לידים ולקוחות פוטנציאליים"
    ),
    "crm_customers": PageConfig(
        page_key="crm_customers",
        title_he="משימות",
        route="/app/crm",
        min_role="agent",
        category="crm",
        api_tags=["customers", "crm"],
        icon="Building2",
        description="ניהול לקוחות ומשימות"
    ),
    
    # Calls
    "calls_inbound": PageConfig(
        page_key="calls_inbound",
        title_he="שיחות נכנסות",
        route="/app/calls",
        min_role="agent",
        category="calls",
        api_tags=["calls", "inbound"],
        icon="Phone",
        description="שיחות נכנסות ותיעוד"
    ),
    "calls_outbound": PageConfig(
        page_key="calls_outbound",
        title_he="שיחות יוצאות",
        route="/app/outbound-calls",
        min_role="agent",
        category="calls",
        api_tags=["calls", "outbound"],
        icon="PhoneOutgoing",
        description="שיחות יוצאות ופרויקטים"
    ),
    
    # WhatsApp
    "whatsapp_inbox": PageConfig(
        page_key="whatsapp_inbox",
        title_he="WhatsApp",
        route="/app/whatsapp",
        min_role="agent",
        category="whatsapp",
        api_tags=["whatsapp", "messages"],
        icon="MessageCircle",
        description="תיבת WhatsApp והודעות"
    ),
    "whatsapp_broadcast": PageConfig(
        page_key="whatsapp_broadcast",
        title_he="תפוצה WhatsApp",
        route="/app/whatsapp-broadcast",
        min_role="admin",
        category="whatsapp",
        api_tags=["whatsapp", "broadcast"],
        icon="Send",
        description="שליחת הודעות המוניות"
    ),
    
    # Communications
    "emails": PageConfig(
        page_key="emails",
        title_he="מיילים",
        route="/app/emails",
        min_role="agent",
        category="communications",
        api_tags=["emails"],
        icon="Mail",
        description="ניהול מיילים"
    ),
    
    # Calendar
    "calendar": PageConfig(
        page_key="calendar",
        title_he="לוח שנה",
        route="/app/calendar",
        min_role="agent",
        category="calendar",
        api_tags=["calendar", "appointments"],
        icon="Calendar",
        description="לוח שנה ופגישות"
    ),
    
    # Reports & Analytics
    "statistics": PageConfig(
        page_key="statistics",
        title_he="סטטיסטיקות",
        route="/app/statistics",
        min_role="agent",
        category="reports",
        api_tags=["statistics", "reports"],
        icon="BarChart3",
        description="דוחות וסטטיסטיקות"
    ),
    
    # Finance (disabled by default)
    "invoices": PageConfig(
        page_key="invoices",
        title_he="חשבוניות",
        route="/app/invoices",
        min_role="admin",
        category="finance",
        api_tags=["invoices", "billing"],
        icon="FileText",
        description="ניהול חשבוניות ותשלומים"
    ),
    "contracts": PageConfig(
        page_key="contracts",
        title_he="חוזים",
        route="/app/contracts",
        min_role="admin",
        category="finance",
        api_tags=["contracts", "billing"],
        icon="FileSignature",
        description="ניהול חוזים"
    ),
    
    # Settings & Management
    "settings": PageConfig(
        page_key="settings",
        title_he="הגדרות מערכת",
        route="/app/settings",
        min_role="agent",
        category="settings",
        api_tags=["settings"],
        icon="Settings",
        description="הגדרות עסק ומערכת"
    ),
    "users": PageConfig(
        page_key="users",
        title_he="ניהול משתמשים",
        route="/app/users",
        min_role="admin",
        category="settings",
        api_tags=["users"],
        icon="UserCog",
        description="ניהול משתמשי העסק"
    ),
    
    # System Admin Only Pages (not included in business permissions)
    "admin_dashboard": PageConfig(
        page_key="admin_dashboard",
        title_he="סקירה כללית - מנהל",
        route="/app/admin/overview",
        min_role="system_admin",
        category="admin",
        api_tags=["admin"],
        icon="LayoutDashboard",
        description="מסך סקירה למנהל מערכת",
        is_system_admin_only=True
    ),
    "admin_businesses": PageConfig(
        page_key="admin_businesses",
        title_he="ניהול עסקים",
        route="/app/admin/businesses",
        min_role="system_admin",
        category="admin",
        api_tags=["admin", "businesses"],
        icon="Building2",
        description="ניהול כל העסקים במערכת",
        is_system_admin_only=True
    ),
    "admin_business_minutes": PageConfig(
        page_key="admin_business_minutes",
        title_he="ניהול דקות",
        route="/app/admin/business-minutes",
        min_role="system_admin",
        category="admin",
        api_tags=["admin", "minutes"],
        icon="Clock",
        description="ניהול דקות שיחה לפי עסק",
        is_system_admin_only=True
    ),
}

def get_all_page_keys(include_system_admin: bool = False) -> List[str]:
    """
    Get all page keys
    
    Args:
        include_system_admin: If True, include system_admin-only pages
        
    Returns:
        List of page keys
    """
    if include_system_admin:
        return list(PAGE_REGISTRY.keys())
    
    return [
        key for key, config in PAGE_REGISTRY.items()
        if not config.is_system_admin_only
    ]

def get_page_config(page_key: str) -> Optional[PageConfig]:
    """Get configuration for a specific page"""
    return PAGE_REGISTRY.get(page_key)

def get_pages_by_category(category: str) -> List[PageConfig]:
    """Get all pages in a specific category"""
    return [
        config for config in PAGE_REGISTRY.values()
        if config.category == category
    ]

def get_all_categories() -> List[str]:
    """Get all unique categories"""
    return list(set(config.category for config in PAGE_REGISTRY.values()))

def get_pages_for_role(role: RoleType, include_system_admin: bool = False) -> List[str]:
    """
    Get all pages accessible for a given role
    
    Args:
        role: User role
        include_system_admin: If True, include system_admin-only pages
        
    Returns:
        List of page keys accessible for this role
    """
    role_hierarchy = {
        "agent": 0,
        "manager": 1,
        "admin": 2,
        "owner": 3,
        "system_admin": 4
    }
    
    user_level = role_hierarchy.get(role, 0)
    
    return [
        key for key, config in PAGE_REGISTRY.items()
        if (include_system_admin or not config.is_system_admin_only)
        and role_hierarchy.get(config.min_role, 0) <= user_level
    ]

def validate_page_keys(page_keys: List[str]) -> tuple[bool, List[str]]:
    """
    Validate that all page keys exist in registry
    
    Returns:
        (is_valid, invalid_keys)
    """
    invalid = [key for key in page_keys if key not in PAGE_REGISTRY]
    return len(invalid) == 0, invalid

# Default pages for new businesses (all non-system-admin pages)
DEFAULT_ENABLED_PAGES = get_all_page_keys(include_system_admin=False)
