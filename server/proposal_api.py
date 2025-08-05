"""
Proposal API endpoints for React frontend
API נקודות עבור מערכת הצעות מחיר עם React
"""
from flask import Blueprint, request, jsonify
from app import db
from models import Proposal, Business
from auth import login_required, AuthService, check_business_access
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create Proposal API Blueprint
proposal_api_bp = Blueprint('proposal_api', __name__, url_prefix='/api/proposal')

def check_business_permission(business, feature):
    """בדיקת הרשאות עסק לתכונה ספציפית"""
    if not getattr(business, feature, False):
        return False
    return True

@proposal_api_bp.route('/proposals', methods=['GET'])
@login_required
def get_proposals():
    """קבלת רשימת הצעות מחיר עבור React"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user:
            return jsonify({'error': 'אין הרשאה לגשת למערכת הצעות'}), 403
        
        # קבלת הצעות לפי העסק
        if current_user.role == 'admin':
            proposals = Proposal.query.order_by(Proposal.created_at.desc()).all()
        else:
            if not current_user.business_id:
                return jsonify({'error': 'משתמש לא משויך לעסק'}), 403
                
            # בדיקת הרשאות עסק
            business = Business.query.get(current_user.business_id)
            if not business or not check_business_permission(business, 'proposal_enabled'):
                return jsonify({'error': 'העסק לא מורשה לשימוש בהצעות מחיר'}), 403
            
            proposals = Proposal.query.filter_by(
                business_id=current_user.business_id
            ).order_by(Proposal.created_at.desc()).all()
        
        # המרת הצעות לפורמט JSON
        proposals_data = []
        for proposal in proposals:
            proposals_data.append({
                'id': proposal.id,
                'customer_name': proposal.customer_name,
                'customer_email': proposal.customer_email,
                'title': proposal.title,
                'description': proposal.description,
                'amount': float(proposal.amount) if proposal.amount else 0,
                'status': proposal.status,
                'valid_until': proposal.valid_until.isoformat() if proposal.valid_until else None,
                'created_at': proposal.created_at.isoformat() if proposal.created_at else None,
                'updated_at': proposal.updated_at.isoformat() if proposal.updated_at else None
            })
        
        # סטטיסטיקות
        total_proposals = len(proposals)
        accepted_count = len([p for p in proposals if p.status == 'accepted'])
        pending_count = len([p for p in proposals if p.status == 'pending'])
        total_amount = sum([float(p.amount) for p in proposals if p.amount and p.status == 'accepted'])
        
        return jsonify({
            'success': True,
            'proposals': proposals_data,
            'stats': {
                'total_proposals': total_proposals,
                'accepted': accepted_count,
                'pending': pending_count,
                'total_amount': total_amount
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting proposals: {e}")
        return jsonify({'error': 'שגיאה בטעינת הצעות'}), 500

@proposal_api_bp.route('/proposals', methods=['POST'])
@login_required
def create_proposal():
    """יצירת הצעת מחיר חדשה"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user:
            return jsonify({'error': 'אין הרשאה ליצור הצעות'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'נתונים לא תקינים'}), 400
        
        customer_name = data.get('customer_name')
        customer_email = data.get('customer_email')
        title = data.get('title')
        description = data.get('description', '')
        amount = data.get('amount')
        valid_until_str = data.get('valid_until')
        
        if not all([customer_name, customer_email, title, amount]):
            return jsonify({'error': 'שם לקוח, אימייל, כותרת וסכום הם שדות חובה'}), 400
        
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return jsonify({'error': 'סכום לא תקין'}), 400
        
        valid_until = None
        if valid_until_str:
            try:
                valid_until = datetime.fromisoformat(valid_until_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'תאריך תוקף לא תקין'}), 400
        
        # קביעת business_id
        business_id = current_user.business_id if current_user.role != 'admin' else data.get('business_id')
        
        if business_id:
            # בדיקת הרשאות עסק
            business = Business.query.get(business_id)
            if not business or not check_business_permission(business, 'proposal_enabled'):
                return jsonify({'error': 'העסק לא מורשה לשימוש בהצעות מחיר'}), 403
        
        # יצירת הצעה חדשה
        proposal = Proposal(
            customer_name=customer_name,
            customer_email=customer_email,
            title=title,
            description=description,
            amount=amount,
            business_id=business_id,
            status='pending',
            valid_until=valid_until
        )
        
        db.session.add(proposal)
        db.session.commit()
        
        logger.info(f"New proposal created: {title} for {customer_name} by {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': f'הצעת מחיר נוצרה בהצלחה עבור {customer_name}',
            'proposal': {
                'id': proposal.id,
                'customer_name': proposal.customer_name,
                'title': proposal.title,
                'amount': float(proposal.amount),
                'status': proposal.status,
                'created_at': proposal.created_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error creating proposal: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה ביצירת הצעה'}), 500

@proposal_api_bp.route('/proposals/<int:proposal_id>/status', methods=['PUT'])
@login_required
def update_proposal_status(proposal_id):
    """עדכון סטטוס הצעת מחיר"""
    try:
        current_user = AuthService.get_current_user()
        
        proposal = Proposal.query.get_or_404(proposal_id)
        
        # בדיקת הרשאות
        if (current_user and current_user.role != 'admin' and 
            current_user.business_id and proposal.business_id != current_user.business_id):
            return jsonify({'error': 'אין הרשאה לעדכן הצעה זו'}), 403
        
        data = request.get_json()
        new_status = data.get('status') if data else None
        
        if new_status not in ['pending', 'accepted', 'rejected']:
            return jsonify({'error': 'סטטוס לא תקין'}), 400
        
        old_status = proposal.status
        proposal.status = new_status
        proposal.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Proposal status updated: {proposal.title} from {old_status} to {new_status} by {current_user.username if current_user else 'unknown'}")
        
        return jsonify({
            'success': True,
            'message': f'סטטוס ההצעה עודכן ל-{new_status}',
            'proposal': {
                'id': proposal.id,
                'status': proposal.status,
                'updated_at': proposal.updated_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating proposal status: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה בעדכון סטטוס הצעה'}), 500