"""
AgentLocator v42 - Digital Signature Routes
ממשק חתימות דיגיטליות לחוזים וחשבוניות
"""

from flask import Blueprint, jsonify, request, Response
import logging
from datetime import datetime
import base64
import hashlib

logger = logging.getLogger(__name__)
signature_bp = Blueprint('signature', __name__)

@signature_bp.route('/contracts/<int:contract_id>/sign', methods=['POST'])
def sign_contract(contract_id):
    """חתימה דיגיטלית על חוזה"""
    try:
        data = request.get_json()
        signature_data = data.get('signature')  # Base64 encoded signature
        signer_name = data.get('signer_name', '')
        signer_ip = request.remote_addr
        
        if not signature_data:
            return jsonify({'error': 'נדרשת חתימה דיגיטלית'}), 400
            
        # יצירת hash של החתימה לאימות
        signature_hash = hashlib.sha256(signature_data.encode()).hexdigest()
        
        # שמירה למסד נתונים
        from utils import get_db_connection
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # עדכון סטטוס החוזה לחתום
        cur.execute("""
            UPDATE contracts 
            SET status = 'signed',
                signature_data = %s,
                signature_hash = %s,
                signed_by = %s,
                signed_at = NOW(),
                signer_ip = %s
            WHERE id = %s
        """, (signature_data, signature_hash, signer_name, signer_ip, contract_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Contract {contract_id} signed by {signer_name}")
        
        return jsonify({
            'success': True,
            'message': 'החוזה נחתם בהצלחה',
            'signature_hash': signature_hash,
            'signed_at': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error signing contract: {e}")
        return jsonify({'error': 'שגיאה בחתימת החוזה'}), 500

@signature_bp.route('/contracts/<int:contract_id>/verify', methods=['GET'])
def verify_signature(contract_id):
    """אימות חתימה דיגיטלית"""
    try:
        from utils import get_db_connection
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        cur.execute("""
            SELECT signature_data, signature_hash, signed_by, 
                   signed_at, signer_ip, status
            FROM contracts 
            WHERE id = %s
        """, (contract_id,))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            return jsonify({'error': 'חוזה לא נמצא'}), 404
        
        if not result[0]:  # No signature data
            return jsonify({
                'signed': False,
                'status': 'לא חתום',
                'message': 'החוזה עדיין לא נחתם'
            }), 200
        
        # אימות integrity של החתימה
        signature_data = result[0]
        stored_hash = result[1]
        calculated_hash = hashlib.sha256(signature_data.encode()).hexdigest()
        
        is_valid = (calculated_hash == stored_hash)
        
        return jsonify({
            'signed': True,
            'valid': is_valid,
            'status': result[5],
            'signed_by': result[2],
            'signed_at': result[3].isoformat() if result[3] else None,
            'signer_ip': result[4],
            'message': 'חתימה תקפה' if is_valid else 'חתימה פגומה'
        }), 200
        
    except Exception as e:
        logger.error(f"Error verifying signature: {e}")
        return jsonify({'error': 'שגיאה באימות החתימה'}), 500

@signature_bp.route('/contracts/<int:contract_id>/certificate', methods=['GET'])
def get_signature_certificate(contract_id):
    """קבלת תעודת חתימה דיגיטלית"""
    try:
        from utils import get_db_connection
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        cur.execute("""
            SELECT c.title, c.signature_hash, c.signed_by, 
                   c.signed_at, c.signer_ip, b.name as business_name
            FROM contracts c
            JOIN business b ON c.business_id = b.id
            WHERE c.id = %s AND c.status = 'signed'
        """, (contract_id,))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            return jsonify({'error': 'חוזה חתום לא נמצא'}), 404
        
        # יצירת תעודת חתימה
        certificate = {
            'contract_id': contract_id,
            'contract_title': result[0],
            'business_name': result[5],
            'signature_hash': result[1],
            'signed_by': result[2],
            'signed_at': result[3].isoformat() if result[3] else None,
            'signer_ip': result[4],
            'certificate_issued_at': datetime.now().isoformat(),
            'certificate_type': 'Digital Signature Certificate',
            'issuer': 'AgentLocator v42 CRM System'
        }
        
        return jsonify(certificate), 200
        
    except Exception as e:
        logger.error(f"Error generating certificate: {e}")
        return jsonify({'error': 'שגיאה ביצירת התעודה'}), 500