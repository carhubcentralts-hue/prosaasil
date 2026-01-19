"""
AI Tools for Assets Library (מאגר)

These tools allow the AI to search and retrieve asset information during conversations.
Tools are only registered if the 'assets' page is enabled for the business.

Tools:
- assets_search: Search assets by query/filters, returns top results with cover images
- assets_get: Get full asset details including all media
- assets_get_media: Get media list for an asset (for WhatsApp image sending)
"""

from pydantic import BaseModel, Field
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class AssetsSearchInput(BaseModel):
    """Input for assets_search tool"""
    business_id: int = Field(..., description="Business ID")
    query: Optional[str] = Field(None, description="Search query for title/description/tags")
    category: Optional[str] = Field(None, description="Filter by category")
    tag: Optional[str] = Field(None, description="Filter by specific tag")
    limit: int = Field(5, description="Maximum results to return (default: 5)")


class AssetSearchResult(BaseModel):
    """Single asset in search results"""
    id: int
    title: str
    short_description: Optional[str] = None
    tags: List[str] = []
    category: Optional[str] = None
    cover_attachment_id: Optional[int] = None


class AssetsSearchOutput(BaseModel):
    """Output for assets_search tool"""
    success: bool = True
    count: int = 0
    items: List[AssetSearchResult] = []
    message: Optional[str] = None


class AssetsGetInput(BaseModel):
    """Input for assets_get tool"""
    business_id: int = Field(..., description="Business ID")
    asset_id: int = Field(..., description="Asset ID to retrieve")


class MediaItem(BaseModel):
    """Media item in asset"""
    attachment_id: int
    role: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None


class AssetsGetOutput(BaseModel):
    """Output for assets_get tool"""
    success: bool = True
    id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    category: Optional[str] = None
    custom_fields: Optional[dict] = None
    media: List[MediaItem] = []
    message: Optional[str] = None


class AssetsGetMediaInput(BaseModel):
    """Input for assets_get_media tool"""
    business_id: int = Field(..., description="Business ID")
    asset_id: int = Field(..., description="Asset ID to get media from")


class AssetsGetMediaOutput(BaseModel):
    """Output for assets_get_media tool"""
    success: bool = True
    count: int = 0
    media: List[MediaItem] = []
    message: Optional[str] = None


def assets_search_impl(business_id: int, query: str = None, category: str = None, 
                        tag: str = None, limit: int = 5) -> AssetsSearchOutput:
    """
    Search assets for a business
    
    Args:
        business_id: Business ID (required for multi-tenant)
        query: Search query for title/description/tags
        category: Filter by category
        tag: Filter by specific tag
        limit: Max results (default: 5)
    
    Returns:
        AssetsSearchOutput with list of matching assets
    """
    try:
        from server.models_sql import AssetItem, AssetItemMedia, db
        from sqlalchemy import or_
        
        # Build query
        q = AssetItem.query.filter_by(
            business_id=business_id,
            status='active'
        )
        
        # Filter by category
        if category:
            q = q.filter_by(category=category)
        
        # Filter by tag
        if tag:
            from sqlalchemy import text
            q = q.filter(text("tags::text LIKE :tag_pattern")).params(tag_pattern=f'%"{tag}"%')
        
        # Search query
        if query:
            search_pattern = f'%{query}%'
            q = q.filter(
                or_(
                    AssetItem.title.ilike(search_pattern),
                    AssetItem.description.ilike(search_pattern),
                    AssetItem.tags.cast(db.String).ilike(search_pattern)
                )
            )
        
        # Limit and order
        q = q.order_by(AssetItem.updated_at.desc()).limit(limit)
        
        items = []
        for asset in q.all():
            # Get cover image
            cover_media = AssetItemMedia.query.filter_by(
                asset_item_id=asset.id,
                role='cover'
            ).first()
            
            cover_attachment_id = None
            if cover_media:
                cover_attachment_id = cover_media.attachment_id
            else:
                # Fall back to first image
                first_media = AssetItemMedia.query.filter_by(
                    asset_item_id=asset.id
                ).order_by(AssetItemMedia.sort_order).first()
                if first_media:
                    cover_attachment_id = first_media.attachment_id
            
            # Truncate description
            short_desc = None
            if asset.description:
                short_desc = asset.description[:100] + '...' if len(asset.description) > 100 else asset.description
            
            items.append(AssetSearchResult(
                id=asset.id,
                title=asset.title,
                short_description=short_desc,
                tags=asset.tags or [],
                category=asset.category,
                cover_attachment_id=cover_attachment_id
            ))
        
        logger.info(f"[ASSETS_TOOL] assets_search business={business_id} query='{query}' results={len(items)}")
        
        return AssetsSearchOutput(
            success=True,
            count=len(items),
            items=items
        )
        
    except Exception as e:
        logger.error(f"[ASSETS_TOOL] assets_search error: {e}", exc_info=True)
        return AssetsSearchOutput(
            success=False,
            message=f"שגיאה בחיפוש במאגר: {str(e)[:50]}"
        )


def assets_get_impl(business_id: int, asset_id: int) -> AssetsGetOutput:
    """
    Get full asset details including all media
    
    Args:
        business_id: Business ID (required for multi-tenant)
        asset_id: Asset ID to retrieve
    
    Returns:
        AssetsGetOutput with full asset details and media
    """
    try:
        from server.models_sql import AssetItem, AssetItemMedia, Attachment
        
        # Get asset with multi-tenant check
        asset = AssetItem.query.filter_by(
            id=asset_id,
            business_id=business_id
        ).first()
        
        if not asset:
            return AssetsGetOutput(
                success=False,
                message="לא מצאתי את הפריט במאגר"
            )
        
        # Get all media
        media_list = []
        media_items = AssetItemMedia.query.filter_by(
            asset_item_id=asset.id
        ).order_by(AssetItemMedia.sort_order).all()
        
        for media in media_items:
            attachment = Attachment.query.get(media.attachment_id)
            if attachment and not attachment.is_deleted:
                media_list.append(MediaItem(
                    attachment_id=attachment.id,
                    role=media.role,
                    filename=attachment.filename_original,
                    mime_type=attachment.mime_type
                ))
        
        logger.info(f"[ASSETS_TOOL] assets_get business={business_id} asset_id={asset_id} media={len(media_list)}")
        
        return AssetsGetOutput(
            success=True,
            id=asset.id,
            title=asset.title,
            description=asset.description,
            tags=asset.tags or [],
            category=asset.category,
            custom_fields=asset.custom_fields,
            media=media_list
        )
        
    except Exception as e:
        logger.error(f"[ASSETS_TOOL] assets_get error: {e}", exc_info=True)
        return AssetsGetOutput(
            success=False,
            message=f"שגיאה בשליפת פריט: {str(e)[:50]}"
        )


def assets_get_media_impl(business_id: int, asset_id: int) -> AssetsGetMediaOutput:
    """
    Get media list for an asset (for WhatsApp sending)
    
    Args:
        business_id: Business ID (required for multi-tenant)
        asset_id: Asset ID to get media from
    
    Returns:
        AssetsGetMediaOutput with list of attachment_ids
    """
    try:
        from server.models_sql import AssetItem, AssetItemMedia, Attachment
        
        # Verify asset belongs to business
        asset = AssetItem.query.filter_by(
            id=asset_id,
            business_id=business_id
        ).first()
        
        if not asset:
            return AssetsGetMediaOutput(
                success=False,
                message="לא מצאתי את הפריט במאגר"
            )
        
        # Get all media
        media_list = []
        media_items = AssetItemMedia.query.filter_by(
            asset_item_id=asset.id
        ).order_by(AssetItemMedia.sort_order).all()
        
        for media in media_items:
            attachment = Attachment.query.get(media.attachment_id)
            if attachment and not attachment.is_deleted:
                media_list.append(MediaItem(
                    attachment_id=attachment.id,
                    role=media.role,
                    filename=attachment.filename_original,
                    mime_type=attachment.mime_type
                ))
        
        logger.info(f"[ASSETS_TOOL] assets_get_media business={business_id} asset_id={asset_id} count={len(media_list)}")
        
        return AssetsGetMediaOutput(
            success=True,
            count=len(media_list),
            media=media_list
        )
        
    except Exception as e:
        logger.error(f"[ASSETS_TOOL] assets_get_media error: {e}", exc_info=True)
        return AssetsGetMediaOutput(
            success=False,
            message=f"שגיאה בשליפת תמונות: {str(e)[:50]}"
        )


def is_assets_enabled(business_id: int) -> bool:
    """
    Check if assets feature is enabled for the business
    
    Args:
        business_id: Business ID to check
    
    Returns:
        True if 'assets' is in enabled_pages, False otherwise
    """
    try:
        from server.models_sql import Business
        
        business = Business.query.get(business_id)
        if not business:
            return False
        
        enabled_pages = business.enabled_pages or []
        return 'assets' in enabled_pages
        
    except Exception as e:
        logger.warning(f"[ASSETS_TOOL] Could not check assets permission: {e}")
        return False
