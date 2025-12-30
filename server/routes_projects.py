"""
Routes for Outbound Projects
Handles project management, lead assignment, and call tracking
"""
from flask import Blueprint, request, jsonify, g
from sqlalchemy import text, func
from server.db import db
from server.auth import require_auth, get_current_tenant
import logging
from datetime import datetime

log = logging.getLogger(__name__)

projects_bp = Blueprint('projects', __name__)


@projects_bp.route('/api/projects', methods=['GET'])
@require_auth
def list_projects():
    """List all projects for the current tenant"""
    try:
        # Use get_current_tenant() to safely get tenant ID
        tenant_id = get_current_tenant()
        if not tenant_id:
            log.error("[Projects] list_projects: No tenant found")
            return jsonify({'success': False, 'error': 'Tenant not found'}), 401
        
        log.info(f"[Projects] list_projects: Using tenant_id={tenant_id}")
        
        # Get pagination params
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 50))
        offset = (page - 1) * page_size
        
        # Get search filter
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        
        # Build query
        query = """
            SELECT 
                p.id, p.name, p.description, p.status,
                p.created_at, p.updated_at, p.started_at, p.completed_at,
                COUNT(DISTINCT pl.lead_id) as total_leads,
                COUNT(DISTINCT cl.call_sid) as total_calls,
                SUM(CASE WHEN cl.status = 'completed' THEN 1 ELSE 0 END) as answered_calls,
                SUM(CASE WHEN cl.status = 'no-answer' THEN 1 ELSE 0 END) as no_answer_calls,
                SUM(CASE WHEN cl.status IN ('busy', 'failed') THEN 1 ELSE 0 END) as failed_calls,
                SUM(cl.duration) as total_duration
            FROM outbound_projects p
            LEFT JOIN project_leads pl ON pl.project_id = p.id
            LEFT JOIN call_log cl ON cl.project_id = p.id AND cl.direction = 'outbound'
            WHERE p.tenant_id = :tenant_id
        """
        params = {'tenant_id': tenant_id}
        
        if search:
            query += " AND p.name ILIKE :search"
            params['search'] = f'%{search}%'
        
        if status_filter:
            query += " AND p.status = :status"
            params['status'] = status_filter
        
        query += """
            GROUP BY p.id
            ORDER BY p.created_at DESC
            LIMIT :limit OFFSET :offset
        """
        params['limit'] = page_size
        params['offset'] = offset
        
        # Execute query
        projects = db.session.execute(text(query), params).fetchall()
        
        # Get total count
        count_query = """
            SELECT COUNT(DISTINCT p.id)
            FROM outbound_projects p
            WHERE p.tenant_id = :tenant_id
        """
        if search:
            count_query += " AND p.name ILIKE :search"
        if status_filter:
            count_query += " AND p.status = :status"
        
        total = db.session.execute(text(count_query), params).scalar() or 0
        
        # Format response
        items = []
        for p in projects:
            items.append({
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'status': p.status,
                'created_at': p.created_at.isoformat() if p.created_at else None,
                'updated_at': p.updated_at.isoformat() if p.updated_at else None,
                'started_at': p.started_at.isoformat() if p.started_at else None,
                'completed_at': p.completed_at.isoformat() if p.completed_at else None,
                'total_leads': p.total_leads or 0,
                'stats': {
                    'total_calls': p.total_calls or 0,
                    'answered': p.answered_calls or 0,
                    'no_answer': p.no_answer_calls or 0,
                    'failed': p.failed_calls or 0,
                    'total_duration': p.total_duration or 0,
                } if p.started_at else None  # Only show stats if project has started
            })
        
        return jsonify({
            'success': True,
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size
        })
    
    except Exception as e:
        log.error(f"[Projects] Error listing projects: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects', methods=['POST'])
@require_auth
def create_project():
    """Create a new project"""
    try:
        # Use get_current_tenant() to safely get tenant ID
        tenant_id = get_current_tenant()
        if not tenant_id:
            log.error("[Projects] create_project: No tenant found")
            return jsonify({'success': False, 'error': 'Tenant not found'}), 401
        
        log.info(f"[Projects] create_project: Using tenant_id={tenant_id}")
        
        user_id = g.user.get('id') if hasattr(g, 'user') and g.user is not None else None
        
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        lead_ids = data.get('lead_ids', [])
        
        if not name:
            return jsonify({'success': False, 'error': 'שם פרויקט חובה'}), 400
        
        # Create project
        result = db.session.execute(text("""
            INSERT INTO outbound_projects (tenant_id, name, description, status, created_by, created_at, updated_at)
            VALUES (:tenant_id, :name, :description, 'draft', :created_by, NOW(), NOW())
            RETURNING id
        """), {
            'tenant_id': tenant_id,
            'name': name,
            'description': description,
            'created_by': user_id
        })
        project_id = result.scalar()
        
        # Add leads to project if provided
        added_count = 0
        skipped_count = 0
        if lead_ids:
            for lead_id in lead_ids:
                # Verify lead belongs to tenant
                lead_check = db.session.execute(text("""
                    SELECT id FROM leads WHERE id = :lead_id AND tenant_id = :tenant_id
                """), {'lead_id': lead_id, 'tenant_id': tenant_id}).scalar()
                
                if lead_check:
                    result = db.session.execute(text("""
                        INSERT INTO project_leads (project_id, lead_id, added_at)
                        VALUES (:project_id, :lead_id, NOW())
                        ON CONFLICT (project_id, lead_id) DO NOTHING
                        RETURNING id
                    """), {'project_id': project_id, 'lead_id': lead_id})
                    
                    if result.fetchone():  # Lead was actually inserted (not a duplicate)
                        added_count += 1
                else:
                    skipped_count += 1
                    log.warning(f"[Projects] Skipped lead {lead_id} - not found or doesn't belong to tenant {tenant_id}")
        
        db.session.commit()
        
        log.info(f"[Projects] Created project {project_id} - Added {added_count} leads, skipped {skipped_count} for tenant {tenant_id}")
        
        # Build appropriate message
        total_requested = len(lead_ids) if lead_ids else 0
        if total_requested == 0:
            message = 'פרויקט נוצר בהצלחה ללא לידים (ניתן להוסיף לידים מאוחר יותר)'
        elif added_count == 0:
            message = f'פרויקט נוצר אך לא נוספו לידים ({skipped_count} לידים לא נמצאו או לא שייכים לחשבון)'
        elif skipped_count > 0:
            message = f'פרויקט נוצר עם {added_count} לידים ({skipped_count} לידים דולגו)'
        else:
            message = f'פרויקט נוצר בהצלחה עם {added_count} לידים'
        
        return jsonify({
            'success': True,
            'project_id': project_id,
            'added_count': added_count,
            'skipped_count': skipped_count,
            'total_requested': total_requested,
            'message': message
        })
    
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        
        # Provide helpful error message if tables don't exist
        if 'outbound_projects' in error_msg and 'does not exist' in error_msg:
            error_msg = 'טבלת הפרויקטים לא קיימת במסד הנתונים. יש להריץ מיגרציות: ./run_migrations.sh או python -m server.db_migrate'
        elif 'project_leads' in error_msg and 'does not exist' in error_msg:
            error_msg = 'טבלת קישורי הלידים לפרויקטים לא קיימת. יש להריץ מיגרציות: ./run_migrations.sh'
        
        log.error(f"[Projects] Error creating project: {e}", exc_info=True)
        return jsonify({'success': False, 'error': error_msg}), 500


@projects_bp.route('/api/projects/<int:project_id>', methods=['GET'])
@require_auth
def get_project(project_id):
    """Get project details with leads and statistics"""
    try:
        # Use get_current_tenant() to safely get tenant ID
        tenant_id = get_current_tenant()
        if not tenant_id:
            log.error("[Projects] get_project: No tenant found")
            return jsonify({'success': False, 'error': 'Tenant not found'}), 401
        
        log.info(f"[Projects] get_project: Using tenant_id={tenant_id}")
        
        # Get project info
        project = db.session.execute(text("""
            SELECT id, name, description, status, created_at, updated_at, started_at, completed_at
            FROM outbound_projects
            WHERE id = :project_id AND tenant_id = :tenant_id
        """), {'project_id': project_id, 'tenant_id': tenant_id}).fetchone()
        
        if not project:
            return jsonify({'success': False, 'error': 'פרויקט לא נמצא'}), 404
        
        # Get leads in project with their call status
        leads = db.session.execute(text("""
            SELECT 
                l.id, l.full_name, l.phone_e164, l.status,
                pl.call_attempts, pl.last_call_at, pl.last_call_status, pl.total_call_duration,
                pl.added_at
            FROM project_leads pl
            JOIN leads l ON l.id = pl.lead_id
            WHERE pl.project_id = :project_id
            ORDER BY pl.added_at DESC
        """), {'project_id': project_id}).fetchall()
        
        # Get project statistics (only if started)
        stats = None
        if project.started_at:
            stats_result = db.session.execute(text("""
                SELECT 
                    COUNT(*) as total_calls,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as answered,
                    SUM(CASE WHEN status = 'no-answer' THEN 1 ELSE 0 END) as no_answer,
                    SUM(CASE WHEN status IN ('busy', 'failed') THEN 1 ELSE 0 END) as failed,
                    SUM(duration) as total_duration,
                    AVG(duration) as avg_duration
                FROM call_log
                WHERE project_id = :project_id AND direction = 'outbound'
            """), {'project_id': project_id}).fetchone()
            
            if stats_result:
                stats = {
                    'total_calls': stats_result.total_calls or 0,
                    'answered': stats_result.answered or 0,
                    'no_answer': stats_result.no_answer or 0,
                    'failed': stats_result.failed or 0,
                    'total_duration': stats_result.total_duration or 0,
                    'avg_duration': int(stats_result.avg_duration) if stats_result.avg_duration else 0
                }
        
        # Format leads
        leads_data = []
        for lead in leads:
            leads_data.append({
                'id': lead.id,
                'full_name': lead.full_name,
                'phone_e164': lead.phone_e164,
                'status': lead.status,
                'call_attempts': lead.call_attempts or 0,
                'last_call_at': lead.last_call_at.isoformat() if lead.last_call_at else None,
                'last_call_status': lead.last_call_status,
                'total_call_duration': lead.total_call_duration or 0,
                'added_at': lead.added_at.isoformat() if lead.added_at else None
            })
        
        return jsonify({
            'success': True,
            'project': {
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'status': project.status,
                'created_at': project.created_at.isoformat() if project.created_at else None,
                'updated_at': project.updated_at.isoformat() if project.updated_at else None,
                'started_at': project.started_at.isoformat() if project.started_at else None,
                'completed_at': project.completed_at.isoformat() if project.completed_at else None,
                'total_leads': len(leads_data),
                'leads': leads_data,
                'stats': stats
            }
        })
    
    except Exception as e:
        log.error(f"[Projects] Error getting project {project_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects/<int:project_id>/leads', methods=['POST'])
@require_auth
def add_leads_to_project(project_id):
    """Add leads to an existing project"""
    try:
        # Use get_current_tenant() to safely get tenant ID
        tenant_id = get_current_tenant()
        if not tenant_id:
            log.error("[Projects] add_leads_to_project: No tenant found")
            return jsonify({'success': False, 'error': 'Tenant not found'}), 401
        
        log.info(f"[Projects] add_leads_to_project: Using tenant_id={tenant_id}")
        
        # Verify project exists and belongs to tenant
        project = db.session.execute(text("""
            SELECT id FROM outbound_projects WHERE id = :project_id AND tenant_id = :tenant_id
        """), {'project_id': project_id, 'tenant_id': tenant_id}).scalar()
        
        if not project:
            return jsonify({'success': False, 'error': 'פרויקט לא נמצא'}), 404
        
        data = request.get_json()
        lead_ids = data.get('lead_ids', [])
        
        if not lead_ids:
            return jsonify({'success': False, 'error': 'לא נבחרו לידים'}), 400
        
        added_count = 0
        for lead_id in lead_ids:
            # Verify lead belongs to tenant
            lead_check = db.session.execute(text("""
                SELECT id FROM leads WHERE id = :lead_id AND tenant_id = :tenant_id
            """), {'lead_id': lead_id, 'tenant_id': tenant_id}).scalar()
            
            if lead_check:
                # Use fetchone() to check if row was actually inserted
                result = db.session.execute(text("""
                    INSERT INTO project_leads (project_id, lead_id, added_at)
                    VALUES (:project_id, :lead_id, NOW())
                    ON CONFLICT (project_id, lead_id) DO NOTHING
                    RETURNING id
                """), {'project_id': project_id, 'lead_id': lead_id})
                
                if result.fetchone():  # Row was inserted
                    added_count += 1
        
        # Update project updated_at
        db.session.execute(text("""
            UPDATE outbound_projects SET updated_at = NOW() WHERE id = :project_id
        """), {'project_id': project_id})
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'added_count': added_count,
            'message': f'{added_count} לידים נוספו לפרויקט'
        })
    
    except Exception as e:
        db.session.rollback()
        log.error(f"[Projects] Error adding leads to project {project_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects/<int:project_id>/remove-leads', methods=['POST'])
@require_auth
def remove_leads_from_project(project_id):
    """Remove leads from a project"""
    try:
        # Use get_current_tenant() to safely get tenant ID
        tenant_id = get_current_tenant()
        if not tenant_id:
            log.error("[Projects] remove_leads_from_project: No tenant found")
            return jsonify({'success': False, 'error': 'Tenant not found'}), 401
        
        log.info(f"[Projects] remove_leads_from_project: Using tenant_id={tenant_id}")
        
        # Verify project exists and belongs to tenant
        project = db.session.execute(text("""
            SELECT id FROM outbound_projects WHERE id = :project_id AND tenant_id = :tenant_id
        """), {'project_id': project_id, 'tenant_id': tenant_id}).scalar()
        
        if not project:
            return jsonify({'success': False, 'error': 'פרויקט לא נמצא'}), 404
        
        data = request.get_json()
        lead_ids = data.get('lead_ids', [])
        
        if not lead_ids:
            return jsonify({'success': False, 'error': 'לא נבחרו לידים'}), 400
        
        # Remove leads
        result = db.session.execute(text("""
            DELETE FROM project_leads
            WHERE project_id = :project_id AND lead_id = ANY(:lead_ids)
        """), {'project_id': project_id, 'lead_ids': lead_ids})
        
        removed_count = result.rowcount
        
        # Update project updated_at
        db.session.execute(text("""
            UPDATE outbound_projects SET updated_at = NOW() WHERE id = :project_id
        """), {'project_id': project_id})
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'removed_count': removed_count,
            'message': f'{removed_count} לידים הוסרו מהפרויקט'
        })
    
    except Exception as e:
        db.session.rollback()
        log.error(f"[Projects] Error removing leads from project {project_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects/<int:project_id>', methods=['PATCH'])
@require_auth
def update_project(project_id):
    """Update project details"""
    try:
        # Use get_current_tenant() to safely get tenant ID
        tenant_id = get_current_tenant()
        if not tenant_id:
            log.error("[Projects] update_project: No tenant found")
            return jsonify({'success': False, 'error': 'Tenant not found'}), 401
        
        log.info(f"[Projects] update_project: Using tenant_id={tenant_id}")
        
        # Verify project exists and belongs to tenant
        project = db.session.execute(text("""
            SELECT id FROM outbound_projects WHERE id = :project_id AND tenant_id = :tenant_id
        """), {'project_id': project_id, 'tenant_id': tenant_id}).scalar()
        
        if not project:
            return jsonify({'success': False, 'error': 'פרויקט לא נמצא'}), 404
        
        data = request.get_json()
        updates = []
        params = {'project_id': project_id}
        
        if 'name' in data:
            updates.append("name = :name")
            params['name'] = data['name'].strip()
        
        if 'description' in data:
            updates.append("description = :description")
            params['description'] = data['description'].strip()
        
        if 'status' in data:
            status = data['status']
            if status not in ['draft', 'active', 'completed', 'paused']:
                return jsonify({'success': False, 'error': 'סטטוס לא תקין'}), 400
            
            updates.append("status = :status")
            params['status'] = status
            
            # Update started_at when moving to active
            if status == 'active':
                updates.append("started_at = COALESCE(started_at, NOW())")
            
            # Update completed_at when moving to completed
            if status == 'completed':
                updates.append("completed_at = NOW()")
        
        if not updates:
            return jsonify({'success': False, 'error': 'אין שדות לעדכון'}), 400
        
        updates.append("updated_at = NOW()")
        
        query = f"""
            UPDATE outbound_projects
            SET {', '.join(updates)}
            WHERE id = :project_id
        """
        
        db.session.execute(text(query), params)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'פרויקט עודכן בהצלחה'
        })
    
    except Exception as e:
        db.session.rollback()
        log.error(f"[Projects] Error updating project {project_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects/<int:project_id>', methods=['DELETE'])
@require_auth
def delete_project(project_id):
    """Delete a project"""
    try:
        # Use get_current_tenant() to safely get tenant ID
        tenant_id = get_current_tenant()
        if not tenant_id:
            log.error("[Projects] delete_project: No tenant found")
            return jsonify({'success': False, 'error': 'Tenant not found'}), 401
        
        log.info(f"[Projects] delete_project: Using tenant_id={tenant_id}")
        
        # Verify project exists and belongs to tenant
        project = db.session.execute(text("""
            SELECT id FROM outbound_projects WHERE id = :project_id AND tenant_id = :tenant_id
        """), {'project_id': project_id, 'tenant_id': tenant_id}).scalar()
        
        if not project:
            return jsonify({'success': False, 'error': 'פרויקט לא נמצא'}), 404
        
        # Delete project (CASCADE will handle project_leads)
        db.session.execute(text("""
            DELETE FROM outbound_projects WHERE id = :project_id
        """), {'project_id': project_id})
        
        db.session.commit()
        
        log.info(f"[Projects] Deleted project {project_id} for tenant {tenant_id}")
        
        return jsonify({
            'success': True,
            'message': 'פרויקט נמחק בהצלחה'
        })
    
    except Exception as e:
        db.session.rollback()
        log.error(f"[Projects] Error deleting project {project_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
