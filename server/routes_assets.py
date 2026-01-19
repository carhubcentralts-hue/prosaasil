"""
Assets Library API Blueprint (מאגר)

Endpoints:
- GET /api/assets - List assets with filtering
- POST /api/assets - Create new asset
- GET /api/assets/{id} - Get asset details with media
- PATCH /api/assets/{id} - Update asset
- POST /api/assets/{id}/media - Add media to asset
- DELETE /api/assets/{id}/media/{media_id} - Remove media from asset
- DELETE /api/assets/{id} - Archive asset (soft delete)

Security:
- Multi-tenant isolation (business_id)
- Permission checks via @require_page_access('assets')
- All queries filtered by business_id
"""

from flask import Blueprint, jsonify, request, g
from server.auth_api import require_api_auth
from server.security.permissions import require_page_access
from server.models_sql import AssetItem, AssetItemMedia, Attachment, Business
from server.db import db
from server.services.attachment_service import get_attachment_service
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

assets_bp = Blueprint("assets", __name__, url_prefix="/api/assets")


def get_current_user_id():
    """Get current user ID from authenticated context"""
    if hasattr(g, 'user') and g.user and isinstance(g.user, dict):
        return g.user.get('id')
    return None


def get_current_business_id():
    """Get current business ID from authenticated context"""
    if hasattr(g, 'tenant') and g.tenant:
        return g.tenant
    if hasattr(g, 'user') and g.user and isinstance(g.user, dict):
        return g.user.get('business_id')
    return None


@assets_bp.route('', methods=['GET'])
@require_api_auth
@require_page_access('assets')
def list_assets():
    """
    List assets for current business with filtering
    
    Query params:
        - q: Search query (title, description, tags)
        - category: Filter by category
        - tag: Filter by specific tag
        - status: Filter by status (active/archived), default: active
        - page: Page number (default: 1)
        - page_size: Items per page (default: 30, max: 100)
    
    Response:
        - 200: List of assets with cover image and media count
        - 403: Permission denied
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Build query
        query = AssetItem.query.filter_by(business_id=business_id)
        
        # Filter by status (default: active)
        status = request.args.get('status', 'active')
        if status in ['active', 'archived']:
            query = query.filter_by(status=status)
        
        # Filter by category
        category = request.args.get('category')
        if category:
            query = query.filter_by(category=category)
        
        # Filter by tag
        tag = request.args.get('tag')
        if tag:
            # Search within JSON array
            from sqlalchemy import text
            query = query.filter(
                text("tags::text LIKE :tag_pattern")
            ).params(tag_pattern=f'%"{tag}"%')
        
        # Search query (title, description, tags)
        q = request.args.get('q')
        if q:
            search_pattern = f'%{q}%'
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    AssetItem.title.ilike(search_pattern),
                    AssetItem.description.ilike(search_pattern),
                    AssetItem.tags.cast(db.String).ilike(search_pattern)
                )
            )
        
        # Order by updated_at DESC
        query = query.order_by(AssetItem.updated_at.desc())
        
        # Pagination
        page = max(1, int(request.args.get('page', 1)))
        page_size = min(100, max(1, int(request.args.get('page_size', 30))))
        
        paginated = query.paginate(page=page, per_page=page_size, error_out=False)
        
        # Build response
        attachment_service = get_attachment_service()
        items = []
        
        for asset in paginated.items:
            # Get cover image
            cover_media = AssetItemMedia.query.filter_by(
                asset_item_id=asset.id,
                role='cover'
            ).first()
            
            cover_attachment_id = None
            cover_preview_url = None
            
            if cover_media:
                cover_attachment_id = cover_media.attachment_id
                attachment = Attachment.query.get(cover_media.attachment_id)
                if attachment and not attachment.is_deleted:
                    cover_preview_url = attachment_service.generate_signed_url(
                        attachment.id, attachment.storage_path, ttl_minutes=15
                    )
            else:
                # Fall back to first gallery image
                first_media = AssetItemMedia.query.filter_by(
                    asset_item_id=asset.id
                ).order_by(AssetItemMedia.sort_order).first()
                
                if first_media:
                    cover_attachment_id = first_media.attachment_id
                    attachment = Attachment.query.get(first_media.attachment_id)
                    if attachment and not attachment.is_deleted:
                        cover_preview_url = attachment_service.generate_signed_url(
                            attachment.id, attachment.storage_path, ttl_minutes=15
                        )
            
            # Count media
            media_count = AssetItemMedia.query.filter_by(asset_item_id=asset.id).count()
            
            items.append({
                'id': asset.id,
                'title': asset.title,
                'description': asset.description,
                'tags': asset.tags or [],
                'category': asset.category,
                'status': asset.status,
                'cover_attachment_id': cover_attachment_id,
                'cover_preview_url': cover_preview_url,
                'media_count': media_count,
                'created_at': asset.created_at.isoformat() if asset.created_at else None,
                'updated_at': asset.updated_at.isoformat() if asset.updated_at else None
            })
        
        return jsonify({
            'items': items,
            'page': page,
            'page_size': page_size,
            'total': paginated.total,
            'pages': paginated.pages
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing assets: {e}", exc_info=True)
        return jsonify({'error': 'Failed to list assets'}), 500


@assets_bp.route('', methods=['POST'])
@require_api_auth
@require_page_access('assets')
def create_asset():
    """
    Create a new asset
    
    Request body:
        - title: Asset title (required)
        - description: Asset description
        - tags: Array of tags
        - category: Category string
        - custom_fields: Object with custom key-value pairs
    
    Response:
        - 201: Asset created
        - 400: Validation error
        - 403: Permission denied
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        data = request.get_json() or {}
        
        # Validate required fields
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        
        if len(title) > 160:
            return jsonify({'error': 'Title must be 160 characters or less'}), 400
        
        # Create asset
        asset = AssetItem(
            business_id=business_id,
            title=title,
            description=data.get('description', '').strip() or None,
            tags=data.get('tags', []),
            category=data.get('category', '').strip() or None,
            custom_fields=data.get('custom_fields'),
            status='active',
            created_by=user_id,
            updated_by=user_id
        )
        
        db.session.add(asset)
        db.session.commit()
        
        logger.info(f"[ASSETS] Created asset id={asset.id} title='{title}' business_id={business_id}")
        
        return jsonify({
            'id': asset.id,
            'title': asset.title,
            'description': asset.description,
            'tags': asset.tags,
            'category': asset.category,
            'status': asset.status,
            'custom_fields': asset.custom_fields,
            'created_at': asset.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating asset: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to create asset'}), 500


@assets_bp.route('/<int:asset_id>', methods=['GET'])
@require_api_auth
@require_page_access('assets')
def get_asset(asset_id):
    """
    Get asset details with full media list
    
    Response:
        - 200: Asset with media list
        - 403: Permission denied
        - 404: Not found
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Get asset (multi-tenant check)
        asset = AssetItem.query.filter_by(
            id=asset_id,
            business_id=business_id
        ).first()
        
        if not asset:
            return jsonify({'error': 'Asset not found'}), 404
        
        # Get all media
        attachment_service = get_attachment_service()
        media_list = []
        
        media_items = AssetItemMedia.query.filter_by(
            asset_item_id=asset.id
        ).order_by(AssetItemMedia.sort_order).all()
        
        for media in media_items:
            attachment = Attachment.query.get(media.attachment_id)
            if attachment and not attachment.is_deleted:
                signed_url = attachment_service.generate_signed_url(
                    attachment.id, attachment.storage_path, ttl_minutes=60
                )
                media_list.append({
                    'id': media.id,
                    'attachment_id': attachment.id,
                    'filename': attachment.filename_original,
                    'mime_type': attachment.mime_type,
                    'file_size': attachment.file_size,
                    'role': media.role,
                    'sort_order': media.sort_order,
                    'signed_url': signed_url,
                    'created_at': media.created_at.isoformat() if media.created_at else None
                })
        
        return jsonify({
            'id': asset.id,
            'title': asset.title,
            'description': asset.description,
            'tags': asset.tags or [],
            'category': asset.category,
            'status': asset.status,
            'custom_fields': asset.custom_fields,
            'media': media_list,
            'created_at': asset.created_at.isoformat() if asset.created_at else None,
            'updated_at': asset.updated_at.isoformat() if asset.updated_at else None,
            'created_by': asset.created_by,
            'updated_by': asset.updated_by
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting asset {asset_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get asset'}), 500


@assets_bp.route('/<int:asset_id>', methods=['PATCH'])
@require_api_auth
@require_page_access('assets')
def update_asset(asset_id):
    """
    Update asset fields (allowlist: title, description, tags, category, status, custom_fields)
    
    Response:
        - 200: Updated asset
        - 400: Validation error
        - 403: Permission denied
        - 404: Not found
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Get asset (multi-tenant check)
        asset = AssetItem.query.filter_by(
            id=asset_id,
            business_id=business_id
        ).first()
        
        if not asset:
            return jsonify({'error': 'Asset not found'}), 404
        
        data = request.get_json() or {}
        
        # Allowlist fields
        allowed_fields = ['title', 'description', 'tags', 'category', 'status', 'custom_fields']
        
        for field in allowed_fields:
            if field in data:
                value = data[field]
                
                # Validate specific fields
                if field == 'title':
                    if not value or not value.strip():
                        return jsonify({'error': 'Title cannot be empty'}), 400
                    if len(value) > 160:
                        return jsonify({'error': 'Title must be 160 characters or less'}), 400
                    value = value.strip()
                
                elif field == 'status':
                    if value not in ['active', 'archived']:
                        return jsonify({'error': 'Status must be active or archived'}), 400
                
                elif field == 'description':
                    value = value.strip() if value else None
                
                elif field == 'category':
                    value = value.strip() if value else None
                
                setattr(asset, field, value)
        
        asset.updated_by = user_id
        asset.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"[ASSETS] Updated asset id={asset_id} business_id={business_id}")
        
        return jsonify({
            'id': asset.id,
            'title': asset.title,
            'description': asset.description,
            'tags': asset.tags,
            'category': asset.category,
            'status': asset.status,
            'custom_fields': asset.custom_fields,
            'updated_at': asset.updated_at.isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating asset {asset_id}: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to update asset'}), 500


@assets_bp.route('/<int:asset_id>/media', methods=['POST'])
@require_api_auth
@require_page_access('assets')
def add_asset_media(asset_id):
    """
    Add media to asset (links existing attachment)
    
    Request body:
        - attachment_id: ID of existing attachment (required)
        - role: cover|gallery|floorplan|other (default: gallery)
        - sort_order: Sort order integer (default: 0)
    
    Response:
        - 201: Media added
        - 400: Validation error
        - 403: Permission denied
        - 404: Asset or attachment not found
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Get asset (multi-tenant check)
        asset = AssetItem.query.filter_by(
            id=asset_id,
            business_id=business_id
        ).first()
        
        if not asset:
            return jsonify({'error': 'Asset not found'}), 404
        
        data = request.get_json() or {}
        
        # Validate attachment_id
        attachment_id = data.get('attachment_id')
        if not attachment_id:
            return jsonify({'error': 'attachment_id is required'}), 400
        
        # Verify attachment exists and belongs to business
        attachment = Attachment.query.filter_by(
            id=attachment_id,
            business_id=business_id,
            is_deleted=False
        ).first()
        
        if not attachment:
            return jsonify({'error': 'Attachment not found or does not belong to your business'}), 404
        
        # Validate role
        role = data.get('role', 'gallery')
        if role not in ['cover', 'gallery', 'floorplan', 'other']:
            return jsonify({'error': 'Invalid role. Must be cover, gallery, floorplan, or other'}), 400
        
        # If setting as cover, remove existing cover
        if role == 'cover':
            existing_cover = AssetItemMedia.query.filter_by(
                asset_item_id=asset.id,
                role='cover'
            ).first()
            if existing_cover:
                existing_cover.role = 'gallery'
        
        # Get sort_order
        sort_order = data.get('sort_order', 0)
        if not isinstance(sort_order, int):
            sort_order = 0
        
        # Check if media already exists
        existing_media = AssetItemMedia.query.filter_by(
            asset_item_id=asset.id,
            attachment_id=attachment_id
        ).first()
        
        if existing_media:
            return jsonify({'error': 'This attachment is already linked to this asset'}), 400
        
        # Create media link
        media = AssetItemMedia(
            business_id=business_id,
            asset_item_id=asset.id,
            attachment_id=attachment_id,
            role=role,
            sort_order=sort_order
        )
        
        db.session.add(media)
        db.session.commit()
        
        # Generate signed URL
        attachment_service = get_attachment_service()
        signed_url = attachment_service.generate_signed_url(
            attachment.id, attachment.storage_path, ttl_minutes=60
        )
        
        logger.info(f"[ASSETS] Added media id={media.id} to asset id={asset.id} attachment_id={attachment_id}")
        
        return jsonify({
            'id': media.id,
            'attachment_id': attachment.id,
            'filename': attachment.filename_original,
            'mime_type': attachment.mime_type,
            'file_size': attachment.file_size,
            'role': media.role,
            'sort_order': media.sort_order,
            'signed_url': signed_url,
            'created_at': media.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"Error adding media to asset {asset_id}: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to add media'}), 500


@assets_bp.route('/<int:asset_id>/media/<int:media_id>', methods=['DELETE'])
@require_api_auth
@require_page_access('assets')
def remove_asset_media(asset_id, media_id):
    """
    Remove media from asset (deletes the association, not the attachment)
    
    Response:
        - 200: Media removed
        - 403: Permission denied
        - 404: Asset or media not found
    """
    try:
        business_id = get_current_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Get asset (multi-tenant check)
        asset = AssetItem.query.filter_by(
            id=asset_id,
            business_id=business_id
        ).first()
        
        if not asset:
            return jsonify({'error': 'Asset not found'}), 404
        
        # Get media (belongs to this asset)
        media = AssetItemMedia.query.filter_by(
            id=media_id,
            asset_item_id=asset.id,
            business_id=business_id
        ).first()
        
        if not media:
            return jsonify({'error': 'Media not found'}), 404
        
        attachment_id = media.attachment_id
        db.session.delete(media)
        db.session.commit()
        
        logger.info(f"[ASSETS] Removed media id={media_id} from asset id={asset_id}")
        
        return jsonify({
            'message': 'Media removed successfully',
            'media_id': media_id,
            'attachment_id': attachment_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error removing media {media_id} from asset {asset_id}: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to remove media'}), 500


@assets_bp.route('/<int:asset_id>', methods=['DELETE'])
@require_api_auth
@require_page_access('assets')
def archive_asset(asset_id):
    """
    Archive asset (soft delete - sets status to 'archived')
    
    Response:
        - 200: Asset archived
        - 403: Permission denied
        - 404: Not found
    """
    try:
        business_id = get_current_business_id()
        user_id = get_current_user_id()
        
        if not business_id:
            return jsonify({'error': 'Business ID not found'}), 403
        
        # Get asset (multi-tenant check)
        asset = AssetItem.query.filter_by(
            id=asset_id,
            business_id=business_id
        ).first()
        
        if not asset:
            return jsonify({'error': 'Asset not found'}), 404
        
        # Archive instead of delete
        asset.status = 'archived'
        asset.updated_by = user_id
        asset.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"[ASSETS] Archived asset id={asset_id} business_id={business_id}")
        
        return jsonify({
            'message': 'Asset archived successfully',
            'id': asset_id,
            'status': 'archived'
        }), 200
        
    except Exception as e:
        logger.error(f"Error archiving asset {asset_id}: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Failed to archive asset'}), 500
