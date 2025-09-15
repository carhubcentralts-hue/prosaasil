from flask import Blueprint, request, jsonify
from server.auth_api import require_api_auth
import uuid
from datetime import datetime

# Blueprint for receipts and contracts
receipts_contracts_bp = Blueprint('receipts_contracts', __name__)

@receipts_contracts_bp.route('/api/receipts', methods=['POST'])
@require_api_auth()
def create_receipt():
    """יצירת חשבונית ללקוח"""
    try:
        data = request.get_json()
        lead_id = data.get('lead_id')
        amount = data.get('amount', 0)
        description = data.get('description', 'שירותי תיווך')
        
        if not lead_id:
            return jsonify({'success': False, 'message': 'Lead ID נדרש'}), 400
            
        if not isinstance(amount, (int, float)) or amount <= 0:
            return jsonify({'success': False, 'message': 'סכום חייב להיות מספר חיובי'}), 400
            
        # יצירת חשבונית פשוטה
        receipt_id = str(uuid.uuid4())
        receipt_data = {
            'id': receipt_id,
            'lead_id': lead_id,
            'amount': amount,
            'description': description,
            'created_at': datetime.now().isoformat(),
            'status': 'created'
        }
        
        # TODO: שמירה בדאטבייס כשנוסיף טבלת חשבוניות
        
        return jsonify({
            'success': True, 
            'message': f'חשבונית נוצרה בסכום {amount:,} ₪',
            'receipt_id': receipt_id,
            'amount': amount
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'שגיאה ביצירת חשבונית: {str(e)}'}), 500

@receipts_contracts_bp.route('/api/contracts', methods=['POST'])
@require_api_auth()
def create_contract():
    """יצירת חוזה ללקוח"""
    try:
        data = request.get_json()
        lead_id = data.get('lead_id')
        contract_type = data.get('type', 'sale')  # sale, rent, mediation, custom
        custom_title = data.get('title', '')
        
        if not lead_id:
            return jsonify({'success': False, 'message': 'Lead ID נדרש'}), 400
            
        # סוגי חוזים
        contract_types = {
            'sale': 'חוזה מכירה',
            'rent': 'חוזה שכירות', 
            'mediation': 'חוזה תיווך',
            'custom': custom_title or 'חוזה מותאם אישית'
        }
        
        contract_name = contract_types.get(contract_type, custom_title or 'חוזה כללי')
        contract_id = str(uuid.uuid4())
        
        contract_data = {
            'id': contract_id,
            'lead_id': lead_id,
            'type': contract_type,
            'name': contract_name,
            'created_at': datetime.now().isoformat(),
            'status': 'draft'
        }
        
        # TODO: שמירה בדאטבייס כשנוסיף טבלת חוזים
        
        return jsonify({
            'success': True,
            'message': f'{contract_name} נוצר בהצלחה',
            'contract_id': contract_id,
            'type': contract_type
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'שגיאה ביצירת חוזה: {str(e)}'}), 500