# server/password_routes.py
from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash
import logging

logger = logging.getLogger(__name__)

password_bp = Blueprint("password", __name__, url_prefix="/api/auth")

@password_bp.route("/change-password", methods=["POST"])
def change_password():
    """שינוי סיסמה למשתמש מחובר"""
    try:
        # בדיקה שהמשתמש מחובר
        if 'user_id' not in session:
            return jsonify({"error": "לא מחובר למערכת"}), 401
        
        data = request.get_json()
        current_password = data.get('currentPassword')
        new_password = data.get('newPassword')
        
        if not current_password or not new_password:
            return jsonify({"error": "חסרים פרטים"}), 400
        
        user_id = session['user_id']
        
        # בדיקת סיסמה נוכחית (בסימולציה - בפרויקט אמיתי זה יהיה מבסיס הנתונים)
        # כאן נבדוק מול המשתמשים הקיימים במערכת
        test_users = {
            1: {
                "email": "admin@shai.com",
                "password_hash": generate_password_hash("admin123"),
                "role": "admin"
            },
            2: {
                "email": "shai@shai-realestate.co.il", 
                "password_hash": generate_password_hash("shai123"),
                "role": "business"
            }
        }
        
        user_data = test_users.get(user_id)
        if not user_data:
            return jsonify({"error": "משתמש לא נמצא"}), 404
        
        # בדיקת סיסמה נוכחית
        if not check_password_hash(user_data['password_hash'], current_password):
            return jsonify({"error": "סיסמה נוכחית שגויה"}), 400
        
        # בדיקת חוזק הסיסמה החדשה
        if len(new_password) < 8:
            return jsonify({"error": "הסיסמה חייבת להכיל לפחות 8 תווים"}), 400
        
        # בפרויקט אמיתי - כאן נעדכן את בסיס הנתונים
        # עדכון הסיסמה (בסימולציה)
        new_password_hash = generate_password_hash(new_password)
        test_users[user_id]['password_hash'] = new_password_hash
        
        logger.info(f"Password changed successfully for user {user_id}")
        
        return jsonify({
            "success": True,
            "message": "הסיסמה שונתה בהצלחה"
        }), 200
        
    except Exception as e:
        logger.error(f"Password change error: {e}")
        return jsonify({"error": "שגיאה פנימית בשרת"}), 500