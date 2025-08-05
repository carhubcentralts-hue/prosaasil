"""
Signature API endpoints for React frontend
API נקודות עבור מערכת חתימות דיגיטליות עם React
"""
from flask import Blueprint, request, jsonify
from app import db
from models import DigitalSignature, Business
from auth import login_required, AuthService, check_business_access
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create Signature API Blueprint
signature_api_bp = Blueprint('signature_api', __name__, url_prefix='/api/signature')

def check_business_permission(business, feature):
    """בדיקת הרשאות עסק לתכונה ספציפית"""
    if not getattr(business, feature, False):
        return False
    return True

@signature_api_bp.route('/signatures', methods=['GET'])
@login_required
def get_signatures():
    """קבלת רשימת חתימות דיגיטליות עבור React"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user:
            return jsonify({'error': 'אין הרשאה לגשת למערכת חתימות'}), 403
        
        # קבלת חתימות לפי העסק
        if current_user.role == 'admin':
            signatures = DigitalSignature.query.order_by(DigitalSignature.created_at.desc()).all()
        else:
            if not current_user.business_id:
                return jsonify({'error': 'משתמש לא משויך לעסק'}), 403
                
            # בדיקת הרשאות עסק
            business = Business.query.get(current_user.business_id)
            if not business or not check_business_permission(business, 'signature_enabled'):
                return jsonify({'error': 'העסק לא מורשה לשימוש בחתימות דיגיטליות'}), 403
            
            signatures = DigitalSignature.query.filter_by(
                business_id=current_user.business_id
            ).order_by(DigitalSignature.created_at.desc()).all()
        
        # המרת חתימות לפורמט JSON
        signatures_data = []
        for sig in signatures:
            signatures_data.append({
                'id': sig.id,
                'document_name': sig.document_name,
                'signer_name': sig.signer_name,
                'signer_email': sig.signer_email,
                'status': sig.status,
                'created_at': sig.created_at.isoformat() if sig.created_at else None,
                'signed_at': sig.signed_at.isoformat() if sig.signed_at else None,
                'document_url': sig.document_url,
                'signature_url': sig.signature_url
            })
        
        # סטטיסטיקות
        total_signatures = len(signatures)
        signed_count = len([s for s in signatures if s.status == 'signed'])
        pending_count = len([s for s in signatures if s.status == 'pending'])
        
        return jsonify({
            'success': True,
            'signatures': signatures_data,
            'stats': {
                'total_signatures': total_signatures,
                'signed': signed_count,
                'pending': pending_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting signatures: {e}")
        return jsonify({'error': 'שגיאה בטעינת חתימות'}), 500

@signature_api_bp.route('/signatures', methods=['POST'])
@login_required
def create_signature():
    """יצירת חתימה דיגיטלית חדשה"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user:
            return jsonify({'error': 'אין הרשאה ליצור חתימות'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'נתונים לא תקינים'}), 400
        
        document_name = data.get('document_name')
        signer_name = data.get('signer_name')
        signer_email = data.get('signer_email')
        document_content = data.get('document_content', '')
        
        if not all([document_name, signer_name, signer_email]):
            return jsonify({'error': 'שם מסמך, שם חותם ואימייל הם שדות חובה'}), 400
        
        # קביעת business_id
        business_id = current_user.business_id if current_user.role != 'admin' else data.get('business_id')
        
        if business_id:
            # בדיקת הרשאות עסק
            business = Business.query.get(business_id)
            if not business or not check_business_permission(business, 'signature_enabled'):
                return jsonify({'error': 'העסק לא מורשה לשימוש בחתימות דיגיטליות'}), 403
        
        # יצירת חתימה חדשה
        signature = DigitalSignature(
            document_name=document_name,
            signer_name=signer_name,
            signer_email=signer_email,
            business_id=business_id,
            status='pending',
            document_content=document_content
        )
        
        db.session.add(signature)
        db.session.commit()
        
        logger.info(f"New signature created: {document_name} for {signer_name} by {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': f'חתימה דיגיטלית נוצרה בהצלחה עבור {signer_name}',
            'signature': {
                'id': signature.id,
                'document_name': signature.document_name,
                'signer_name': signature.signer_name,
                'signer_email': signature.signer_email,
                'status': signature.status,
                'created_at': signature.created_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error creating signature: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה ביצירת חתימה'}), 500

@signature_api_bp.route('/signatures/<int:signature_id>/sign', methods=['POST'])
@login_required
def sign_document(signature_id):
    """חתימה על מסמך"""
    try:
        current_user = AuthService.get_current_user()
        
        signature = DigitalSignature.query.get_or_404(signature_id)
        
        # בדיקת הרשאות
        if (current_user and current_user.role != 'admin' and 
            current_user.business_id and signature.business_id != current_user.business_id):
            return jsonify({'error': 'אין הרשאה לחתום על מסמך זה'}), 403
        
        data = request.get_json()
        signature_data = data.get('signature_data') if data else None
        
        # עדכון סטטוס החתימה
        signature.status = 'signed'
        signature.signed_at = datetime.utcnow()
        signature.signature_data = signature_data
        
        db.session.commit()
        
        logger.info(f"Document signed: {signature.document_name} by {current_user.username if current_user else 'unknown'}")
        
        return jsonify({
            'success': True,
            'message': 'המסמך נחתם בהצלחה',
            'signature': {
                'id': signature.id,
                'status': signature.status,
                'signed_at': signature.signed_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error signing document: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה בחתימת המסמך'}), 500