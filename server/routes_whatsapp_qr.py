from flask import Blueprint, jsonify
from server.auth_api import require_api_auth
from server.whatsapp_provider import BaileysProvider
import logging
import requests
import base64
import urllib.parse

# Blueprint for WhatsApp QR code
whatsapp_qr_bp = Blueprint('whatsapp_qr', __name__)

@whatsapp_qr_bp.route('/api/whatsapp/baileys/qr', methods=['GET'])
@require_api_auth()
def get_whatsapp_qr():
    """יצירת QR קוד אמיתי לחיבור וואטסאפ באמצעות Baileys"""
    logger = logging.getLogger(__name__)
    
    try:
        # יצירת provider של Baileys
        baileys_provider = BaileysProvider()
        
        # בדיקת זמינות השירות
        if not baileys_provider._check_health():
            logger.warning("Baileys service is not available")
            return jsonify({
                'success': False,
                'message': 'שירות WhatsApp אינו זמין כרגע. אנא נסה שוב מאוחר יותר.',
                'status': 'service_unavailable'
            }), 503
        
        # בקשת QR קוד אמיתי מהשירות
        try:
            response = requests.get(
                f"{baileys_provider.outbound_url}/qr",
                timeout=baileys_provider.timeout
            )
            
            if response.status_code == 200:
                qr_data = response.json()
                
                if qr_data.get('success') and qr_data.get('qrCode'):
                    # יצירת QR קוד ויזואלי מהמידע הצפוני
                    qr_string = qr_data['qrCode']
                    
                    # שימוש בשירות חיצוני ליצירת תמונת QR
                    qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(qr_string)}"
                    
                    image_response = requests.get(qr_image_url, timeout=10)
                    if image_response.status_code == 200:
                        qr_base64 = base64.b64encode(image_response.content).decode('utf-8')
                        
                        logger.info("Real WhatsApp QR code generated successfully")
                        return jsonify({
                            'success': True,
                            'qr': f'data:image/png;base64,{qr_base64}',
                            'status': 'ready',
                            'message': 'סרוק את ה-QR קוד עם WhatsApp כדי להתחבר למערכת',
                            'qr_data': qr_string  # המידע הצפוני עצמו
                        })
                    else:
                        # אם נכשלה יצירת התמונה, החזר את המידע הגולמי
                        return jsonify({
                            'success': True,
                            'qr': qr_string,
                            'status': 'ready',
                            'message': 'QR קוד זמין (טקסט בלבד)',
                            'qr_data': qr_string  # Keep for backwards compatibility
                        })
                        
                elif qr_data.get('success') and not qr_data.get('qrCode'):
                    # כבר מחובר
                    return jsonify({
                        'success': True,
                        'status': 'connected',
                        'message': 'WhatsApp כבר מחובר למערכת'
                    })
                else:
                    # QR לא זמין
                    return jsonify({
                        'success': False,
                        'status': 'qr_unavailable',
                        'message': qr_data.get('message', 'QR קוד אינו זמין כרגע')
                    })
                    
            else:
                logger.error(f"Failed to get QR from Baileys: {response.status_code} {response.text}")
                return jsonify({
                    'success': False,
                    'message': 'שגיאה בקבלת QR קוד מהשירות',
                    'status': 'baileys_error'
                }), 500
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error connecting to Baileys: {e}")
            return jsonify({
                'success': False,
                'message': 'שגיאה בחיבור לשירות WhatsApp',
                'status': 'connection_error'
            }), 503
            
    except Exception as e:
        logger.error(f"Unexpected error in get_whatsapp_qr: {e}")
        return jsonify({
            'success': False, 
            'message': f'שגיאה לא צפויה: {str(e)}',
            'status': 'internal_error'
        }), 500

@whatsapp_qr_bp.route('/api/whatsapp/baileys/status', methods=['GET'])
@require_api_auth()  
def get_whatsapp_status():
    """בדיקת סטטוס חיבור אמיתי של וואטסאפ"""
    logger = logging.getLogger(__name__)
    
    try:
        # יצירת provider של Baileys
        baileys_provider = BaileysProvider()
        
        # בדיקת זמינות השירות
        if not baileys_provider._check_health():
            return jsonify({
                'connected': False,
                'status': 'service_unavailable',
                'message': 'שירות WhatsApp אינו זמין',
                'ready': False
            })
        
        # בקשת סטטוס אמיתי מהשירות
        try:
            response = requests.get(
                f"{baileys_provider.outbound_url}/status",
                timeout=baileys_provider.timeout
            )
            
            if response.status_code == 200:
                status_data = response.json()
                
                connected = status_data.get('connected', False)
                connection_state = status_data.get('state', 'unknown')
                last_connected = status_data.get('lastConnected')
                
                # הודעה בעברית בהתאם לסטטוס
                if connected:
                    message = 'WhatsApp מחובר בהצלחה למערכת'
                elif connection_state == 'connecting':
                    message = 'מתחבר ל-WhatsApp...'
                elif connection_state == 'disconnected':
                    message = 'WhatsApp מנותק - יש לסרוק QR קוד'
                else:
                    message = f'סטטוס חיבור: {connection_state}'
                
                return jsonify({
                    'connected': connected,
                    'status': connection_state,
                    'message': message,
                    'ready': connected,
                    'last_connected': last_connected,
                    'uptime': status_data.get('uptime'),
                    'messages_cached': status_data.get('messagesCached'),
                    'service_healthy': True
                })
            else:
                logger.error(f"Failed to get status from Baileys: {response.status_code}")
                return jsonify({
                    'connected': False,
                    'status': 'error',
                    'message': 'שגיאה בקבלת סטטוס מהשירות',
                    'ready': False,
                    'service_healthy': False
                }), 500
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error getting status from Baileys: {e}")
            return jsonify({
                'connected': False,
                'status': 'connection_error',
                'message': 'שגיאה בחיבור לשירות WhatsApp',
                'ready': False,
                'service_healthy': False
            })
            
    except Exception as e:
        logger.error(f"Unexpected error in get_whatsapp_status: {e}")
        return jsonify({
            'connected': False,
            'status': 'internal_error', 
            'message': f'שגיאה לא צפויה: {str(e)}',
            'ready': False,
            'service_healthy': False
        }), 500