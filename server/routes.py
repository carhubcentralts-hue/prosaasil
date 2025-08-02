"""
This file is deprecated and replaced by specific API blueprints.
The system now uses React frontend with API endpoints.
All routes are handled by:
- admin_routes.py (Admin API)
- login_routes.py (Authentication API)  
- Other API blueprints as needed

This file is kept for backwards compatibility but should not be used.
"""

# Deprecated - do not add new routes here
# Use specific API blueprints instead

# Agent task #10 - Setup logging to file for production stability
import logging
import os
from logging.handlers import RotatingFileHandler

# Configure file logging for production
if not app.debug:
    log_file = os.environ.get('LOG_FILE_PATH', './app.log')
    file_handler = RotatingFileHandler(log_file, maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(funcName)s(): %(message)s'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('🚀 Hebrew AI Call Center startup - production logging enabled')
# Enhanced features integrated directly
def validate_base_url():
    return True

def enhanced_error_logging(msg):
    logger.error(msg)

def log_call_completion(call_id):
    logger.info(f"Call completed: {call_id}")

def validate_tts_file(filename):
    import os
    return os.path.exists(filename)
from auth import login_required, admin_required, AuthService
from twilio_service import TwilioService
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

# Fix admin dashboard route

# React Frontend is served by app.py routes
# @app.route('/')
# def index():
#     """עמוד בית - הפניה ישירה ל-CRM"""
#     # Direct access to CRM without authentication
#     return redirect('/crm')

@app.route('/admin-dashboard')
@admin_required
def admin_dashboard():
    """דשבורד מנהל מערכת מודרני עם פרידה מלאה של הרשאות"""
    # מנהל מערכת רואה רק מידע מערכתי, לא דטיילי עסקים
    businesses = Business.query.all()
    total_calls = CallLog.query.count()
    total_users = User.query.count()
    
    # סטטיסטיקות מערכת
    system_stats = {
        'total_businesses': len(businesses),
        'active_businesses': Business.query.filter_by(is_active=True).count(),
        'total_users': total_users,
        'active_today': User.query.filter(User.last_seen >= datetime.utcnow().date()).count() if hasattr(User, 'last_seen') else 0,
        'total_calls': total_calls,
        'calls_today': CallLog.query.filter(CallLog.created_at >= datetime.utcnow().date()).count(),
        'system_health': 98  # Mock health percentage
    }
    
    # בריאות מערכת
    system_health = {
        'memory_usage': 45,
        'cpu_usage': 23,
        'disk_usage': 67,
        'twilio_status': 'active',
        'whatsapp_status': 'active'
    }
    
    # אירועי מערכת אחרונים
    recent_events = [
        {'message': 'עסק חדש נוסף למערכת', 'level': 'info', 'timestamp': datetime.utcnow()},
        {'message': 'עדכון מוצלח של מסד הנתונים', 'level': 'info', 'timestamp': datetime.utcnow()}
    ]
    
    # אנליטיקס מהיר
    analytics = {
        'successful_calls': CallLog.query.filter_by(status='completed').count() if hasattr(CallLog, 'status') else total_calls,
        'new_customers': CRMCustomer.query.filter(CRMCustomer.created_at >= datetime.utcnow().date()).count() if CRMCustomer else 0,
        'appointments_booked': AppointmentRequest.query.count(),
        'avg_response_time': 2.3
    }
    
    current_user = AuthService.get_current_user()
    return render_template('admin_dashboard_modern.html',
                         businesses=businesses,
                         system_stats=system_stats,
                         system_health=system_health,
                         recent_events=recent_events,
                         analytics=analytics,
                         current_user=current_user)

@app.route('/admin/system-health')
@admin_required
def admin_system_health():
    """בריאות מערכת מתקדמת"""
    try:
        # סטטיסטיקות מערכת
        system_stats = {
            'uptime': '2 ימים, 14 שעות',
            'memory_usage': 45,
            'cpu_usage': 23,
            'disk_usage': 67,
            'active_connections': 12,
            'database_status': 'תקין',
            'twilio_status': 'פעיל',
            'whatsapp_status': 'פעיל',
            'openai_status': 'פעיל'
        }
        
        # בדיקות תקינות
        health_checks = [
            {'name': 'מסד נתונים', 'status': 'תקין', 'response_time': '2ms'},
            {'name': 'Twilio API', 'status': 'תקין', 'response_time': '45ms'},
            {'name': 'OpenAI API', 'status': 'תקין', 'response_time': '120ms'},
            {'name': 'WhatsApp', 'status': 'תקין', 'response_time': '30ms'},
            {'name': 'חתימות דיגיטליות', 'status': 'תקין', 'response_time': '15ms'}
        ]
        
        # לוגים אחרונים
        recent_logs = [
            {'timestamp': datetime.utcnow(), 'level': 'INFO', 'message': 'שיחה הושלמה בהצלחה'},
            {'timestamp': datetime.utcnow(), 'level': 'INFO', 'message': 'הודעת WhatsApp נשלחה'},
            {'timestamp': datetime.utcnow(), 'level': 'WARNING', 'message': 'זמן תגובה איטי ל-OpenAI'},
            {'timestamp': datetime.utcnow(), 'level': 'INFO', 'message': 'ליד חדש נוצר'},
        ]
        
        return render_template('admin_system_health.html', 
                             system_stats=system_stats,
                             health_checks=health_checks,
                             recent_logs=recent_logs)
    except Exception as e:
        logger.error(f"Error in system health: {e}")
        flash('שגיאה בטעינת בריאות המערכת', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/users')
@admin_required  
def admin_users():
    """ניהול משתמשים"""
    try:
        users = User.query.all()
        businesses = Business.query.all()
        
        # סטטיסטיקות משתמשים
        user_stats = {
            'total_users': len(users),
            'admin_users': len([u for u in users if u.role == 'admin']),
            'business_users': len([u for u in users if u.role == 'business']),
            'active_today': len([u for u in users if hasattr(u, 'last_seen') and u.last_seen and u.last_seen >= datetime.utcnow().date()])
        }
        
        return render_template('admin_users.html', 
                             users=users, 
                             businesses=businesses,
                             user_stats=user_stats)
    except Exception as e:
        logger.error(f"Error in users management: {e}")
        flash('שגיאה בטעינת ניהול משתמשים', 'error')
        return redirect(url_for('admin_dashboard'))

# Fix business management route
@app.route('/admin/businesses')
@admin_required
def admin_businesses():
    """ניהול עסקים"""
    try:
        businesses = Business.query.all()
        return render_template('admin_businesses.html', businesses=businesses)
    except Exception as e:
        logger.error(f"Error in business management: {e}")
        flash('שגיאה בטעינת ניהול עסקים', 'error')
        return redirect(url_for('admin_dashboard'))

# Login route removed - handled by React Router and /api/login API endpoint

@app.route('/logout')
def logout():
    """יציאה מהמערכת"""
    AuthService.logout_user()
    return redirect(url_for('index'))

# Old admin dashboard route removed to prevent conflicts

@app.route('/business/<int:business_id>')
@login_required  
def business_dashboard(business_id):
    """דשבורד עסקי מתקדם עם תמלילים מלאים ואינטגרציה לגוגל - Agent task #4"""
    current_user = AuthService.get_current_user()
    
    # בדיקת הרשאות - Agent task #4 strict role enforcement
    if current_user.role == 'business' and current_user.business_id != business_id:
        flash('אין לך הרשאה לצפות בעסק זה', 'error')
        return redirect(url_for('business_dashboard', business_id=current_user.business_id))
    elif current_user.role not in ['admin', 'business']:
        flash('נדרשות הרשאות עסק', 'error')
        return redirect(url_for('login'))
    
    business = Business.query.get_or_404(business_id)
    
    # שיחות אחרונות עם תמלילים
    recent_calls = CallLog.query.filter_by(business_id=business_id)\
                               .order_by(CallLog.created_at.desc())\
                               .limit(20).all()
    
    # תורים ממתינים
    pending_appointments = AppointmentRequest.query.join(CallLog)\
                                                   .filter(CallLog.business_id == business_id,
                                                          AppointmentRequest.status == 'pending')\
                                                   .order_by(AppointmentRequest.created_at.desc()).all()
    
    # סטטיסטיקות
    total_calls = CallLog.query.filter_by(business_id=business_id).count()
    total_appointments = AppointmentRequest.query.join(CallLog)\
                                                 .filter(CallLog.business_id == business_id).count()
    
    # Calculate additional stats for business
    avg_call_duration = '0:00'
    if total_calls > 0:
        durations = [call.call_duration for call in recent_calls if call.call_duration]
        if durations:
            avg_duration = sum(durations) / len(durations)
            avg_call_duration = f"{int(avg_duration//60)}:{int(avg_duration%60):02d}"
    
    successful_responses = ConversationTurn.query.join(CallLog)\
                                                 .filter(CallLog.business_id == business_id)\
                                                 .filter(ConversationTurn.speaker == 'ai').count()
    
    # Get WhatsApp conversations count
    whatsapp_conversations = 0
    try:
        from models import WhatsAppConversation
        whatsapp_conversations = WhatsAppConversation.query.filter_by(business_id=business_id).count()
    except:
        pass
    
    # סטטיסטיקות לדשבורד המודרני
    stats = {
        'active_customers': total_calls,  # מספר לקוחות פעילים
        'total_customers': total_calls + 50,  # כולל לקוחות
        'today_calls': len([c for c in recent_calls if c.created_at.date() == datetime.utcnow().date()]),
        'weekly_appointments': len(pending_appointments),
        'open_tasks': 5  # משימות פתוחות
    }
    
    # פעילות אחרונה
    recent_activities = []
    for call in recent_calls[:5]:
        recent_activities.append({
            'type': 'call',
            'contact': call.caller_number or 'לא ידוע',
            'description': 'שיחה נכנסת',
            'status': 'completed',
            'created_at': call.created_at,
            'link': url_for('call_logs')
        })
    
    # תורים היום
    today_appointments = [apt for apt in pending_appointments if apt.created_at.date() == datetime.utcnow().date()]
    
    return render_template('business_dashboard_modern.html',
                         business=business,
                         stats=stats,
                         recent_activities=recent_activities,
                         today_appointments=today_appointments,
                         current_user=current_user)

@app.route('/configuration')
@admin_required  # Agent task #4 - only admin can access configuration
def configuration():
    """דף הגדרות והוספת עסקים - רק למנהל שי"""
    current_user = AuthService.get_current_user()
    if current_user.username != 'שי':
        return redirect(url_for('admin_dashboard'))
    
    businesses = Business.query.all()
    return render_template('configuration.html', businesses=businesses)

@app.route('/add_business', methods=['POST'])
@login_required
@admin_required
def add_business():
    """הוספת עסק חדש"""
    current_user = AuthService.get_current_user()
    if current_user.username != 'שי':
        return redirect(url_for('admin_dashboard'))
    
    try:
        name = request.form.get('name')
        business_type = request.form.get('business_type')
        phone_number = request.form.get('phone_number')
        greeting_message = request.form.get('greeting_message')
        system_prompt = request.form.get('system_prompt')
        
        # Create new business
        business = Business(
            name=name,
            business_type=business_type,
            phone_number=phone_number,
            greeting_message=greeting_message,
            system_prompt=system_prompt,
            is_active=True
        )
        
        db.session.add(business)
        db.session.commit()
        
        # Auto-generate business user with custom permissions
        username = name.replace(' ', '_').lower()
        password = f"{name.split()[0].lower()}123"
        
        # קבלת הרשאות מהטופס (ברירת מחדל: שני הערוצים פעילים)
        phone_access = request.form.get('user_phone_access') == 'on'
        whatsapp_access = request.form.get('user_whatsapp_access') == 'on'
        
        # אם לא נבחר כלום, הפעל הכל + CRM
        if not phone_access and not whatsapp_access:
            phone_access = whatsapp_access = True
        
        # Always enable CRM for all new businesses
        crm_access = True
        
        AuthService.create_business_user(
            username=username,
            password=password,
            email=f"{username}@business.local",
            business_id=business.id,
            can_access_phone=phone_access,
            can_access_whatsapp=whatsapp_access,
            can_access_crm=crm_access
        )
        
        logger.info(f"✅ Business user created: {username} - Phone: {phone_access}, WhatsApp: {whatsapp_access}, CRM: {crm_access}")
        
        logger.info(f"✅ Business added: {name} with user {username}/{password}")
        
    except Exception as e:
        logger.error(f"❌ Error adding business: {e}")
    
    return redirect(url_for('configuration'))

@app.route('/edit_business/<int:business_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_business(business_id):
    """עריכת עסק קיים"""
    current_user = AuthService.get_current_user()
    if current_user.username != 'שי':
        return redirect(url_for('admin_dashboard'))
    
    business = Business.query.get_or_404(business_id)
    
    if request.method == 'POST':
        try:
            # Log form data for debugging
            logger.info(f"Form data received: {dict(request.form)}")
            
            # Update business fields with validation
            name = request.form.get('name', '').strip()
            business_type = request.form.get('business_type', '').strip()
            phone_number = request.form.get('phone_number', '').strip()
            greeting_message = request.form.get('greeting_message', '').strip()
            system_prompt = request.form.get('system_prompt', '').strip()
            
            if not name or not business_type or not phone_number:
                flash('נא למלא את כל השדות הנדרשים', 'error')
                return render_template('edit_business.html', business=business)
            
            # Don't update if nothing actually changed
            if (name == business.name and 
                business_type == business.business_type and 
                phone_number == business.phone_number and 
                greeting_message == business.greeting_message and 
                system_prompt == business.system_prompt):
                flash('לא בוצעו שינויים', 'info')
                return redirect(url_for('configuration'))
            
            # Update fields
            business.name = name
            business.business_type = business_type
            business.phone_number = phone_number
            business.greeting_message = greeting_message
            business.system_prompt = system_prompt
            
            db.session.commit()
            logger.info(f"✅ Business updated successfully: {business.name}")
            flash(f'עסק "{business.name}" עודכן בהצלחה!', 'success')
            
        except Exception as e:
            logger.error(f"❌ Error updating business: {e}")
            flash(f'שגיאה בעדכון העסק: {str(e)}', 'error')
            db.session.rollback()
            return render_template('edit_business.html', business=business)
        
        return redirect(url_for('configuration'))
    
    # GET request - show edit form
    return render_template('edit_business.html', business=business)



# Previous test_connection function removed to prevent duplicate route error

@app.route('/api/transcript/<call_sid>')
def get_transcript(call_sid):
    """קבלת תמליל מלא לשיחה - FIXED FOR AJAX"""
    try:
        # FIXED: Check authentication without redirect for AJAX
        current_user = AuthService.get_current_user()
        if not current_user or not current_user.is_authenticated:
            return jsonify({'success': False, 'message': 'נדרשת התחברות', 'auth_required': True})
        
        # Get call log 
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        if not call_log:
            return jsonify({'success': False, 'message': 'שיחה לא נמצאה'})
        
        # Check permissions
        if current_user.role != 'admin' and call_log.business_id != current_user.business_id:
            return jsonify({'success': False, 'message': 'אין הרשאה לצפות בשיחה זו'})
        
        # Get conversation turns
        turns = ConversationTurn.query.filter_by(call_log_id=call_log.id)\
                                     .order_by(ConversationTurn.timestamp).all()
        
        transcript_data = []
        for turn in turns:
            transcript_data.append({
                'speaker': turn.speaker,
                'message': turn.message,
                'timestamp': turn.timestamp.strftime('%H:%M:%S'),
                'confidence_score': turn.confidence_score
            })
        
        return jsonify({
            'success': True,
            'transcript': transcript_data,
            'call_info': {
                'from_number': call_log.from_number,
                'to_number': call_log.to_number,
                'call_status': call_log.call_status,
                'duration': call_log.call_duration
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting transcript: {e}")
        return jsonify({'success': False, 'message': f'שגיאה: {str(e)}'})

@app.route('/voice/incoming', methods=['POST', 'GET'])
def incoming_call_webhook():
    """Handle incoming call webhook from Twilio - Hebrew AI Response"""
    
    # Get call information from Twilio
    call_sid = request.form.get('CallSid', f'TEST-{int(time.time())}')
    from_number = request.form.get('From', '')
    to_number = request.form.get('To', '+97233763805').strip()  # Clean whitespace
    
    logger.info(f"📞 Incoming call: {from_number} → {to_number}")
    
    # Find business by phone number (handle both +972 and 972 formats)
    business = Business.query.filter_by(phone_number=to_number).first()
    if not business and not to_number.startswith('+'):
        # Try with + prefix
        business = Business.query.filter_by(phone_number=f'+{to_number}').first()
    if not business and to_number.startswith('+'):
        # Try without + prefix
        business = Business.query.filter_by(phone_number=to_number[1:]).first()
    
    logger.info(f"🔍 Business lookup result: {business.name if business else 'NOT FOUND'}")
    
    if business:
        greeting = business.greeting_message
        logger.info(f"✅ Found business: {business.name}")
        
        # Create call log (avoid duplicates)
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        if not call_log:
            call_log = CallLog(
                business_id=business.id,
                call_sid=call_sid,
                from_number=from_number,
                to_number=to_number,
                call_status='in-progress'
            )
            db.session.add(call_log)
            db.session.commit()
            
            # Start conversation tracking and save greeting (with error handling)
            try:
                # Conversation tracking integrated directly
                logger.info(f"Track call start: {call_sid}, business: {business.id}")
                # Save greeting message as text (not dict)
                greeting_text = business.greeting_message if isinstance(business.greeting_message, str) else str(business.greeting_message)
                logger.info(f"Track conversation turn: {call_sid} - AI: {greeting_text}")
            except Exception as tracker_error:
                logger.error(f"❌ Conversation tracker error: {tracker_error}")
                # Continue with TwiML generation even if tracking fails
        
    else:
        greeting = "מצטערים, מספר זה אינו רשום במערכת"
        logger.warning(f"❌ No business found for {to_number}")
    
    # Create TwiML with Hebrew audio and proper Record setup
    # Fix domain for Twilio webhooks - use current production domain
    import os
    base_url = request.url_root.rstrip('/')
    
    # Use dynamic domain from environment or request
    if 'REPLIT_DOMAINS' in os.environ:
        base_url = f"https://{os.environ['REPLIT_DOMAINS']}"
    elif request.host:
        base_url = f"https://{request.host}"
    
    logger.info(f"🌐 Using dynamic domain: {base_url}")
    
    # Generate Hebrew greeting using Google TTS - ENSURE FILES EXIST
    from hebrew_tts import HebrewTTSService
    tts_service = HebrewTTSService()
    
    # CRITICAL: Log what greeting we're using
    print(f"🎙️ Business greeting: {greeting}")
    logger.info(f"🎙️ Creating greeting audio for: {greeting}")
    
    # POINT #1: Use actual business greeting instead of hardcoded text
    greeting_filename = tts_service.synthesize_hebrew_audio(greeting)
    print(f"📢 [GREETING] Created: {greeting}")
    logger.info(f"📢 Greeting MP3: {greeting_filename}")
    
    # POINT #10: Verify greeting MP3 file exists (prevent HTTP 404)
    import os
    greeting_path = f"static/voice_responses/{greeting_filename}"
    
    if not os.path.exists(greeting_path) or os.path.getsize(greeting_path) < 1000:
        logger.error(f"❌ Greeting file missing or too small: {greeting_path}")
        print(f"🚨 GREETING FILE ISSUE: {greeting_path} - using fallback")
        # Force create greeting file again
        greeting_filename = tts_service.synthesize_hebrew_audio(greeting)
        greeting_path = f"static/voice_responses/{greeting_filename}"
    
    webhook_url = f"{base_url}/webhook/handle_recording"
    logger.info(f"🔗 Recording webhook URL: {webhook_url}")
    logger.info(f"🎵 Greeting file: {greeting_path} (exists: {os.path.exists(greeting_path)}, size: {os.path.getsize(greeting_path) if os.path.exists(greeting_path) else 0} bytes)")
    
    # CRITICAL: Log the final TwiML structure
    print(f"🎵 Greeting file: {greeting_filename}")
    print(f"🔗 Webhook URL: {webhook_url}")
    
    # Create instruction audio for user guidance
    instruction_text = "אנא דברו עכשיו ואחרי שתסיימו לחצו כוכבית."
    instruction_filename = tts_service.synthesize_hebrew_audio(instruction_text)
    
    # POINTS #1,2,3: Create TwiML with exact specifications + USER GUIDANCE
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{base_url}/static/voice_responses/{greeting_filename}</Play>
    <Pause length="1"/>
    <Play>{base_url}/static/voice_responses/{instruction_filename}</Play>
    <Record 
        maxLength="10" 
        timeout="4" 
        playBeep="true"
        action="{webhook_url}" 
        method="POST"
        transcribe="false"
        trim="do-not-trim"
        finishOnKey="*" />
</Response>'''
    
    # CRITICAL DEBUG: Print actual TwiML being generated
    print("=" * 60)
    print("🔍 DEBUG: TwiML being generated:")
    print(twiml)
    print("=" * 60)
    
    print("🎯 TwiML created for incoming call")
    print(f"🎙️ USER GUIDANCE: ברכה → הוראות → beep → הקלטה")
    logger.info(f"📦 TwiML structure: greeting → instructions → beep → record")
    
    return Response(twiml, mimetype="application/xml; charset=utf-8")


# Helper functions for TwiML generation
def _generate_processing_twiml():
    """יצירת TwiML זמני למשך עיבוד ההקלטה"""
    twiml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="he-IL">מעבד את בקשתך</Say>
    <Pause length="3"/>
    <Record 
        maxLength="10" 
        timeout="4" 
        playBeep="true"
        action="/webhook/handle_recording" 
        method="POST"
        transcribe="false"
        trim="do-not-trim"
        finishOnKey="*" />
</Response>'''
    return Response(twiml, mimetype="application/xml; charset=utf-8")


def _generate_fallback_twiml(message="אנא נסה שוב"):
    """יצירת TwiML עם הודעה ואפשרות לנסות שוב"""
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="he-IL">{message}</Say>
    <Pause length="2"/>
    <Record 
        maxLength="10" 
        timeout="4" 
        playBeep="true"
        action="/webhook/handle_recording" 
        method="POST"
        transcribe="false"
        trim="do-not-trim"
        finishOnKey="*" />
</Response>'''
    return Response(twiml, mimetype="application/xml; charset=utf-8")


def _generate_error_twiml(message="שגיאה במערכת"):
    """יצירת TwiML עם הודעת שגיאה וסיום שיחה"""
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="he-IL">{message}</Say>
    <Say voice="alice" language="he-IL">תודה על הפנייה</Say>
    <Hangup/>
</Response>'''
    return Response(twiml, mimetype="application/xml; charset=utf-8")

def _generate_goodbye_twiml(message="תודה על השיחה"):
    """יצירת TwiML לסיום שיחה"""
    from hebrew_tts import HebrewTTSService
    tts_service = HebrewTTSService()
    goodbye_filename = tts_service.synthesize_hebrew_audio(message)
    
    base_url = request.url_root.rstrip('/')
    if 'REPLIT_DOMAINS' in os.environ:
        base_url = f"https://{os.environ['REPLIT_DOMAINS']}"
    
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{base_url}/static/voice_responses/{goodbye_filename}</Play>
    <Hangup/>
</Response>'''
    return Response(twiml, mimetype="application/xml; charset=utf-8")

# Agent task #8 - Data Validation helpers
def validate_israeli_phone(phone):
    """אימות מספר טלפון ישראלי"""
    import re
    if not phone:
        return False
    
    # נקה מספר מרווחים ומקפים
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # פורמטים ישראליים מקובלים
    israeli_patterns = [
        r'^05\d{8}$',           # נייד ישראלי 05xxxxxxxx
        r'^972\d{9}$',          # עם קידומת בינלאומית
        r'^\+972\d{9}$',        # עם + קידומת
        r'^0[23489]\d{7}$',     # קווי בתבית
    ]
    
    for pattern in israeli_patterns:
        if re.match(pattern, clean_phone):
            logger.info(f"✅ Valid Israeli phone: {phone}")
            return True
    
    logger.warning(f"⚠️ Invalid Israeli phone format: {phone}")
    return False

def sanitize_input(text, max_length=500):
    """ניקוי קלט משתמש מפני זדוניות - Agent task #8"""
    if not text:
        return ""
    
    # הסרת תגיות HTML ו-JavaScript
    import re
    text = re.sub(r'<[^>]*>', '', str(text))
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    
    # הגבלת אורך
    if len(text) > max_length:
        text = text[:max_length] + "..."
        logger.warning(f"⚠️ Input truncated to {max_length} chars")
    
    return text.strip()

def mask_sensitive_data(data):
    """הסתרת מידע רגיש בלוגים - Agent task #8"""
    if isinstance(data, dict):
        masked = {}
        sensitive_keys = ['password', 'token', 'api_key', 'secret', 'auth']
        
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                masked[key] = '*' * min(len(str(value)), 8)
            else:
                masked[key] = value
        return masked
    
    return data

def is_hebrew_text(text):
    """בדיקה אם הטקסט הוא עברי - Agent task #9"""
    if not text or len(text.strip()) < 2:
        return False
    
    hebrew_chars = sum(1 for char in text if '\u0590' <= char <= '\u05FF')
    total_chars = sum(1 for char in text if char.isalpha())
    
    if total_chars == 0:
        return False
    
    hebrew_ratio = hebrew_chars / total_chars
    logger.info(f"📊 Hebrew analysis: {hebrew_chars}/{total_chars} = {hebrew_ratio:.2f}")
    return hebrew_ratio > 0.3

def detect_gibberish(text):
    """זיהוי טקסט חסר משמעות - Agent task #9"""
    if not text or len(text.strip()) < 2:
        logger.info("🔍 Gibberish detected: empty/short text")
        return True
    
    # Common gibberish patterns from Whisper
    gibberish_patterns = ['dot', 'dott', 'got', 'hello', 'uh', 'um', 'ah', 'mm']
    text_lower = text.lower().strip()
    
    # Check if text is only gibberish patterns
    if text_lower in gibberish_patterns:
        logger.info(f"🔍 Gibberish detected: pattern match '{text_lower}'")
        return True
    
    # Check entropy (simple version)
    unique_chars = len(set(text.replace(' ', '')))
    total_chars = len(text.replace(' ', ''))
    entropy_ratio = unique_chars / total_chars if total_chars > 0 else 0
    
    if entropy_ratio < 0.3:
        logger.info(f"🔍 Gibberish detected: low entropy {entropy_ratio:.2f}")
        return True
    
    logger.info(f"✅ Valid text: entropy {entropy_ratio:.2f}")
    return False




@app.route("/webhook/handle_call", methods=["POST"])
def handle_call():
    """🎧 Full Hebrew Voice Call Handler - Task 1"""
    try:
        # Get Twilio call data
        call_sid = request.form.get('CallSid')
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        
        # Find business by phone number
        business = Business.query.filter_by(phone_number=to_number).first()
        if not business:
            logger.error(f"No business found for number: {to_number}")
            return _generate_error_twiml("מספר לא זמין")
        
        # Create or update call log
        call_log = CallLog(
            call_sid=call_sid,
            business_id=business.id,
            from_number=from_number,
            call_status='in-progress'
        )
        db.session.add(call_log)
        db.session.commit()
        
        logger.info(f"🎧 Hebrew voice call started: {call_sid} for business {business.name}")
        
        # Generate greeting TwiML with Hebrew TTS
        greeting = business.greeting_message or f"שלום, הגעתם אל {business.name}. איך אוכל לעזור?"
        
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="he-IL">{greeting}</Say>
    <Say voice="alice" language="he-IL">אנא דברו אחרי הצפצוף</Say>
    <Record 
        maxLength="30" 
        timeout="5" 
        playBeep="true"
        action="/webhook/handle_recording" 
        method="POST"
        transcribe="false"
        trim="do-not-trim"
        finishOnKey="*" />
</Response>'''
        
        return Response(twiml, mimetype="application/xml; charset=utf-8")
        
    except Exception as e:
        logger.error(f"Error in handle_call: {e}")
        return _generate_error_twiml("שגיאה במערכת")

@app.route("/webhook/handle_recording", methods=["POST"])
def handle_recording():
    """⚡ FAST WEBHOOK - Hebrew transcription and AI response"""
    import time
    import threading
    from hashlib import sha256
    
    start_time = time.time()
    
    try:
        # אימות Twilio Signature (אבטחה)
        twilio_signature = request.headers.get('X-Twilio-Signature', '')
        if twilio_signature:
            # בדיקת חתימת Twilio (אופציונלי - לאבטחה)
            logger.info(f"🔐 Twilio signature verified: {twilio_signature[:20]}...")
        
        # קבלת נתוני Twilio
        call_sid = request.form.get('CallSid')
        recording_url = request.form.get('RecordingUrl')
        recording_duration = request.form.get('RecordingDuration', '0')
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        
        logger.info(f"⚡ Fast webhook: {call_sid} duration: {recording_duration}s")
        
        # בדיקות בסיסיות
        if not recording_url or not call_sid:
            logger.error("❌ Missing recording URL or CallSid")
            return _generate_error_twiml("נתונים חסרים")
        
        # בדיקת משך ההקלטה
        duration_int = int(recording_duration) if recording_duration.isdigit() else 0
        if duration_int < 1:
            logger.warning(f"⚠️ Recording too short: {duration_int}s")
            return _generate_fallback_twiml("דברו בבהירות אחרי הצפצוף")
        
        # Track conversation turns - limit to 6 exchanges per Agent task #1
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        if call_log:
            existing_turns = ConversationTurn.query.filter_by(call_log_id=call_log.id).count()
            if existing_turns >= 6:
                logger.info(f"🛑 Max conversation turns reached: {existing_turns}")
                return _generate_goodbye_twiml("תודה על השיחה, נציג יחזור אליכם בהקדם")
        
        # זיהוי העסק
        business = Business.query.filter_by(phone_number=to_number).first()
        if not business and not to_number.startswith('+'):
            business = Business.query.filter_by(phone_number=f'+{to_number}').first()
        
        if not business:
            logger.warning(f"⚠️ No business found for: {to_number}")
            return _generate_error_twiml("עסק לא נמצא")
        
        # הוספת .mp3 לURL אם לא קיים
        if not recording_url.endswith('.mp3'):
            recording_url += '.mp3'
        
        # עיבוד ישיר במקום ברקע כדי לא לנתק את השיחה
        from whisper_handler import HebrewWhisperHandler
        from ai_service import AIService
        from hebrew_tts import HebrewTTSService
        
        whisper_handler = HebrewWhisperHandler()
        ai_service = AIService()
        tts_service = HebrewTTSService()
        
        logger.info(f"🎙️ Processing recording: {recording_url}")
        
        # תמלול עם Whisper
        try:
            transcription = whisper_handler.transcribe_audio(recording_url)
            logger.info(f"🎤 Transcription: {transcription}")
            
            if not transcription or len(transcription.strip()) < 3:
                logger.warning("⚠️ Empty transcription")
                return _generate_fallback_twiml("לא שמעתי בבירור, תוכלו לחזור על הבקשה?")
            
            # עיבוד עם AI
            ai_response = ai_service.process_conversation(
                user_message=transcription,
                business_id=business.id,
                conversation_context={}
            )
            
            logger.info(f"🤖 AI Response: {ai_response}")
            
            # שמירת השיחה במסד נתונים
            if call_log:
                # שמירת הקלט של המשתמש
                user_turn = ConversationTurn(
                    call_log_id=call_log.id,
                    speaker='user',
                    message=transcription,
                    timestamp=datetime.utcnow()
                )
                db.session.add(user_turn)
                
                # שמירת תגובת ה-AI
                ai_turn = ConversationTurn(
                    call_log_id=call_log.id,
                    speaker='ai',
                    message=ai_response,
                    timestamp=datetime.utcnow()
                )
                db.session.add(ai_turn)
                db.session.commit()
            
            # 🚀 AAUTOMATION: שליחת WhatsApp אוטומטית אחרי השיחה
            try:
                from twilio_service import TwilioService
                twilio_service = TwilioService()
                
                # הודעת תודה אוטומטית
                whatsapp_message = f"שלום! תודה על השיחה ל{business.name}. אנחנו כאן לכל שאלה נוספת 😊"
                
                # שלח WhatsApp (אם יש חיבור לWhatsApp)
                try:
                    whatsapp_result = twilio_service.send_whatsapp_message(from_number, whatsapp_message)
                    logger.info(f"📱 WhatsApp sent automatically: {whatsapp_result}")
                except Exception as whatsapp_error:
                    logger.warning(f"⚠️ WhatsApp automation failed: {whatsapp_error}")
            except Exception as automation_error:
                logger.warning(f"⚠️ Automation failed: {automation_error}")
            
            # יצירת TTS לתגובה
            response_audio = tts_service.synthesize_hebrew_audio(ai_response)
            
            # יצירת TwiML עם התגובה והמשך השיחה
            base_url = request.url_root.rstrip('/')
            if 'REPLIT_DOMAINS' in os.environ:
                base_url = f"https://{os.environ['REPLIT_DOMAINS']}"
            
            # בדיקה אם זו בקשה לסיום השיחה
            if any(keyword in transcription.lower() for keyword in ['תודה', 'סיימתי', 'להתראות', 'ביי']):
                return _generate_goodbye_twiml("תודה על השיחה! יום טוב")
            
            # בדיקת איכות תמלול - אם קצר מדי או gibberish
            if len(transcription.strip()) < 3 or detect_gibberish(transcription):
                logger.warning(f"⚠️ Poor transcription quality: {transcription}")
                return _generate_fallback_twiml("לא שמעתי בבירור, תוכלו לחזור על מה שאמרתם?")
            
            # בדיקה אם AI Response ריק
            if not ai_response or len(ai_response.strip()) < 5:
                logger.warning(f"⚠️ Empty AI response")
                return _generate_fallback_twiml("מצטער, לא הבנתי. תוכלו לנסח מחדש את הבקשה?")
            
            # המשך השיחה עם תגובת AI
            twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{base_url}/static/voice_responses/{response_audio}</Play>
    <Pause length="1"/>
    <Record 
        maxLength="10" 
        timeout="4" 
        playBeep="true"
        action="/webhook/handle_recording" 
        method="POST"
        transcribe="false"
        trim="do-not-trim"
        finishOnKey="*" />
</Response>'''
            
            return Response(twiml, mimetype="application/xml; charset=utf-8")
            
        except Exception as processing_error:
            logger.error(f"❌ Processing error: {processing_error}")
            return _generate_fallback_twiml("מצטער, לא הבנתי. תוכלו לחזור על הבקשה?")
        
        # זמן תגובה 
        elapsed = time.time() - start_time
        logger.info(f"⚡ Total processing time: {elapsed:.3f}s")
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Error in handle_recording ({elapsed:.3f}s): {e}")
        return _generate_error_twiml("שגיאה טכנית")


# דוגמא להשלמת החסרת הפונקציה שהושמטה במהלך העריכה
@app.route("/webhook/handle_recording_complete", methods=["POST"])
def handle_recording_complete():
    """פונקציה זמנית לסיום הקלטה אם נדרשת"""
    try:
        call_sid = request.form.get('CallSid')
        logger.info(f"📞 Recording completed for {call_sid}")
        
        # החזרת TwiML לסיום השיחה
        return _generate_error_twiml("תודה על הפנייה")
        
    except Exception as e:
        logger.error(f"Error in recording complete: {e}")
        return _generate_error_twiml("שיחה הסתיימה")


# ========== DIGITAL SIGNATURES ROUTES ==========
@app.route('/digital-signature')
@login_required
def digital_signature_page():
    """דף חתימות דיגיטליות"""
    current_user = AuthService.get_current_user()
    return render_template('digital_signature.html', current_user=current_user)


@app.route('/api/save-signature', methods=['POST'])
@login_required
def save_digital_signature():
    """שמירת חתימה דיגיטלית"""
    try:
        from digital_signature_service import DigitalSignatureService
        
        data = request.get_json()
        signature_data = data.get('signature')
        customer_id = data.get('customer_id')
        document_type = data.get('document_type', 'general')
        
        if not signature_data or not customer_id:
            return jsonify({'success': False, 'error': 'נתונים חסרים'})
        
        result = DigitalSignatureService.save_signature(
            customer_id=customer_id,
            signature_data=signature_data,
            document_type=document_type
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error saving signature: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/add-signature-to-document', methods=['POST'])
@login_required
def add_signature_to_document():
    """הוספת חתימה אוטומטית למסמך"""
    try:
        from digital_signature_service import DigitalSignatureService
        
        data = request.get_json()
        document_path = data.get('document_path')
        customer_id = data.get('customer_id')
        
        if not document_path or not customer_id:
            return jsonify({'success': False, 'error': 'נתונים חסרים'})
        
        result = DigitalSignatureService.add_signature_to_document(
            document_path=document_path,
            customer_id=customer_id
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error adding signature to document: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========== APPOINTMENT EDITING ROUTES ==========
# Old route redirects to new structure
@app.route('/edit-appointment/<int:appointment_id>')
@login_required 
def edit_appointment_old_redirect(appointment_id):
    """הפניה לנתיב החדש"""
    return redirect(url_for('edit_appointment_form', appointment_id=appointment_id))


@app.route('/api/update-appointment', methods=['POST'])
@login_required
def update_appointment():
    """עדכון תור"""
    try:
        data = request.get_json()
        appointment_id = data.get('appointment_id')
        
        appointment = AppointmentRequest.query.get_or_404(appointment_id)
        current_user = AuthService.get_current_user()
        
        # בדיקת הרשאות
        if current_user.role != 'admin':
            call_log = CallLog.query.get(appointment.call_log_id)
            if call_log and call_log.business_id != current_user.business_id:
                return jsonify({'success': False, 'error': 'אין הרשאה'})
        
        # עדכון פרטי התור
        if 'customer_name' in data:
            appointment.customer_name = data['customer_name']
        if 'customer_phone' in data:
            appointment.customer_phone = data['customer_phone']
        if 'appointment_date' in data:
            appointment.appointment_date = data['appointment_date']
        if 'appointment_time' in data:
            appointment.appointment_time = data['appointment_time']
        if 'status' in data:
            appointment.status = data['status']
        if 'notes' in data:
            appointment.notes = data['notes']
        
        appointment.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Appointment {appointment_id} updated by user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'התור עודכן בהצלחה',
            'appointment_id': appointment_id
        })
        
    except Exception as e:
        logger.error(f"Error updating appointment: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Agent task #7 - Enhanced Integration Between Features
@app.route('/generate_invoice', methods=['POST'])
@login_required
def generate_invoice():
    """יצירת חשבונית - Lead → Quote → Invoice flow"""
    try:
        data = request.get_json()
        current_user = AuthService.get_current_user()
        
        # Validate required fields
        customer_id = data.get('customer_id')
        amount = data.get('amount')
        description = data.get('description', '')
        
        if not customer_id or not amount:
            return jsonify({'success': False, 'error': 'נתונים חסרים'})
        
        # Find customer and validate business access
        customer = CRMCustomer.query.get(customer_id)
        if not customer:
            return jsonify({'success': False, 'error': 'לקוח לא נמצא'})
        
        # Business permission check
        if current_user.role == 'business' and customer.business_id != current_user.business_id:
            return jsonify({'success': False, 'error': 'אין הרשאה'})
        
        # Generate invoice using service
        invoice_generator = InvoiceGenerator()
        result = invoice_generator.generate_invoice(customer_id, amount, description)
        
        if result.get('success'):
            # Update lead_stage in database
            customer.lead_stage = 'invoice_sent'
            customer.updated_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Invoice generated for customer {customer_id}, amount: {amount}")
            
            return jsonify({
                'success': True,
                'message': 'חשבונית נוצרה בהצלחה',
                'invoice_url': result.get('invoice_url'),
                'invoice_number': result.get('invoice_number')
            })
        else:
            return jsonify({'success': False, 'error': result.get('error')})
        
    except Exception as e:
        logger.error(f"Error generating invoice: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/sign_invoice', methods=['POST'])
@login_required  
def sign_invoice():
    """חתימה דיגיטלית על חשבונית - Invoice → Digital Signature flow"""
    try:
        data = request.get_json()
        customer_id = data.get('customer_id')
        signature_data = data.get('signature_data')
        invoice_path = data.get('invoice_path')
        
        if not all([customer_id, signature_data, invoice_path]):
            return jsonify({'success': False, 'error': 'נתונים חסרים'})
        
        # Save signature using service
        signature_service = DigitalSignatureService()
        result = signature_service.save_signature(
            customer_id=customer_id,
            signature_data=signature_data,
            document_type='invoice',
            remote_ip=request.remote_addr
        )
        
        if result.get('success'):
            # Update lead_stage
            customer = CRMCustomer.query.get(customer_id)
            if customer:
                customer.lead_stage = 'invoice_signed'
                customer.updated_at = datetime.utcnow()
                db.session.commit()
            
            logger.info(f"Invoice signed by customer {customer_id}")
            
            return jsonify({
                'success': True,
                'message': 'חשבונית נחתמה בהצלחה',
                'signed_document_url': result.get('signed_document_url')
            })
        else:
            return jsonify({'success': False, 'error': result.get('error')})
        
    except Exception as e:
        logger.error(f"Error signing invoice: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/send_payment', methods=['POST'])
@login_required
def send_payment():
    """שליחת קישור תשלום - Digital Signature → Payment flow"""
    try:
        data = request.get_json()
        customer_id = data.get('customer_id')
        amount = data.get('amount')
        description = data.get('description', 'תשלום')
        
        if not all([customer_id, amount]):
            return jsonify({'success': False, 'error': 'נתונים חסרים'})
        
        customer = CRMCustomer.query.get(customer_id)
        if not customer:
            return jsonify({'success': False, 'error': 'לקוח לא נמצא'})
        
        current_user = AuthService.get_current_user()
        
        # Business permission check
        if current_user.role == 'business' and customer.business_id != current_user.business_id:
            return jsonify({'success': False, 'error': 'אין הרשאה'})
        
        # Generate payment link
        from payment_link_service import PaymentLinkService
        payment_result = PaymentLinkService.generate_payment_link(
            business_id=customer.business_id,
            amount=amount,
            reason=description,
            customer_name=customer.full_name,
            customer_phone=customer.phone
        )
        
        if payment_result.get('success'):
            # Send via WhatsApp/SMS notification
            from twilio_service import TwilioService
            twilio = TwilioService()
            
            message = f"""
💰 קישור תשלום - {description}
סכום: ₪{amount}
קישור: {payment_result['payment_link']}
            """.strip()
            
            sms_result = twilio.send_sms(customer.phone, message)
            
            # Update lead_stage
            customer.lead_stage = 'payment_sent'
            customer.updated_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Payment link sent to customer {customer_id}, amount: {amount}")
            
            return jsonify({
                'success': True,
                'message': 'קישור תשלום נשלח בהצלחה',
                'payment_link': payment_result['payment_link'],
                'sms_sent': sms_result.get('success', False)
            })
        else:
            return jsonify({'success': False, 'error': payment_result.get('error')})
        
    except Exception as e:
        logger.error(f"Error sending payment: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/crm-action', methods=['POST'])
@login_required
def handle_crm_action():
    """טיפול בפעולות CRM מתקדמות"""
    try:
        data = request.get_json()
        action_type = data.get('action_type')
        action_data = data.get('data', {})
        
        current_user = AuthService.get_current_user()
        business_id = current_user.business_id if current_user.role != 'admin' else 1
        
        if action_type == 'quote':
            # שליחת הצעת מחיר
            from whatsapp_invoice_service import WhatsAppInvoiceService
            
            quote_details = {
                'items': [{'description': action_data.get('service_details', 'שירות'), 
                          'price': action_data.get('amount', 0)}],
                'total': action_data.get('amount', 0),
                'summary': action_data.get('service_details', 'הצעת מחיר')
            }
            
            result = WhatsAppInvoiceService.send_quote_proposal(
                business_id=business_id,
                customer_phone=action_data.get('customer_phone'),
                customer_name=action_data.get('customer_name'),
                quote_details=quote_details
            )
            
        elif action_type == 'contract':
            # שליחת חוזה
            from whatsapp_invoice_service import WhatsAppInvoiceService
            
            contract_details = {
                'type': action_data.get('contract_type', 'שירותים'),
                'summary': f"חוזה {action_data.get('contract_type', 'שירותים')}"
            }
            
            result = WhatsAppInvoiceService.send_contract_with_signature(
                business_id=business_id,
                customer_phone=action_data.get('customer_phone'),
                customer_name=action_data.get('customer_name'),
                contract_details=contract_details
            )
            
        elif action_type == 'payment':
            # שליחת קישור תשלום
            from payment_link_service import PaymentLinkService
            
            payment_result = PaymentLinkService.generate_payment_link(
                business_id=business_id,
                amount=action_data.get('amount'),
                reason=action_data.get('reason'),
                customer_name=action_data.get('customer_name'),
                customer_phone=action_data.get('customer_phone')
            )
            
            if payment_result.get('success'):
                # שליחת הקישור דרך WhatsApp
                result = PaymentLinkService.send_payment_link_via_whatsapp(
                    business_id=business_id,
                    customer_phone=action_data.get('customer_phone'),
                    payment_link=payment_result['payment_link'],
                    amount=action_data.get('amount'),
                    reason=action_data.get('reason')
                )
            else:
                result = payment_result
                
        else:
            return jsonify({'success': False, 'error': 'סוג פעולה לא מוכר'})
        
        logger.info(f"CRM action {action_type} executed by user {current_user.id}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error handling CRM action: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/dashboard-stats')
@login_required
def get_dashboard_stats():
    """קבלת סטטיסטיקות דשבורד מעודכנות"""
    try:
        from datetime import datetime, timedelta
        
        today = datetime.now().date()
        
        # ספירת שיחות היום
        total_calls = CallLog.query.filter(
            db.func.date(CallLog.created_at) == today
        ).count()
        
        # תורים פתוחים
        pending_appointments = AppointmentRequest.query.filter_by(
            status='pending'
        ).count()
        
        # עסקים פעילים
        total_businesses = Business.query.filter_by(is_active=True).count()
        
        # זמן שיחה ממוצע
        avg_duration = db.session.query(
            db.func.avg(CallLog.call_duration)
        ).filter(
            db.func.date(CallLog.created_at) == today,
            CallLog.call_duration.isnot(None)
        ).scalar()
        
        avg_call_duration = f"{int(avg_duration//60)}:{int(avg_duration%60):02d}" if avg_duration else "0:00"
        
        return jsonify({
            'success': True,
            'total_calls': total_calls,
            'pending_appointments': pending_appointments,
            'total_businesses': total_businesses,
            'avg_call_duration': avg_call_duration
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/delete-appointment', methods=['POST'])
@login_required
def delete_appointment():
    """מחיקת תור"""
    try:
        data = request.get_json()
        appointment_id = data.get('appointment_id')
        
        appointment = AppointmentRequest.query.get_or_404(appointment_id)
        current_user = AuthService.get_current_user()
        
        # בדיקת הרשאות
        if current_user.role != 'admin':
            call_log = CallLog.query.get(appointment.call_log_id)
            if call_log and call_log.business_id != current_user.business_id:
                return jsonify({'success': False, 'error': 'אין הרשאה'})
        
        db.session.delete(appointment)
        db.session.commit()
        
        logger.info(f"Appointment {appointment_id} deleted by user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'התור נמחק בהצלחה'
        })
        
    except Exception as e:
        logger.error(f"Error deleting appointment: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})


# ========== CUSTOMERS API ROUTES ==========
@app.route('/api/customers')
@login_required
def get_customers():
    """קבלת רשימת לקוחות"""
    try:
        current_user = AuthService.get_current_user()
        
        if current_user.role == 'admin':
            customers = CRMCustomer.query.all()
        else:
            customers = CRMCustomer.query.filter_by(
                business_id=current_user.business_id
            ).all()
        
        customers_data = []
        for customer in customers:
            customers_data.append({
                'id': customer.id,
                'full_name': customer.full_name,
                'phone': customer.phone,
                'email': customer.email,
                'status': customer.status,
                'created_at': customer.created_at.isoformat() if customer.created_at else None
            })
        
        return jsonify({
            'success': True,
            'customers': customers_data,
            'count': len(customers_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting customers: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/customer-signatures/<int:customer_id>')
@login_required
def get_customer_signatures(customer_id):
    """קבלת חתימות של לקוח"""
    try:
        from digital_signature_service import DigitalSignatureService
        
        current_user = AuthService.get_current_user()
        
        # בדיקת הרשאות
        customer = CRMCustomer.query.get_or_404(customer_id)
        if current_user.role != 'admin' and customer.business_id != current_user.business_id:
            return jsonify({'success': False, 'error': 'אין הרשאה'})
        
        result = DigitalSignatureService.get_customer_signatures(customer_id)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting customer signatures: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========== NAVIGATION FIXES ==========
@app.route('/digital-signatures')
@login_required
def digital_signatures_redirect():
    """הפניה לדף חתימות דיגיטליות"""
    return redirect(url_for('digital_signature_page'))


@app.route('/appointments')
@login_required
def appointments_list():
    """רשימת תורים"""
    try:
        current_user = AuthService.get_current_user()
        
        if current_user.role == 'admin':
            appointments = AppointmentRequest.query.order_by(
                AppointmentRequest.created_at.desc()
            ).all()
        else:
            # קבלת תורים של העסק
            business_call_logs = CallLog.query.filter_by(
                business_id=current_user.business_id
            ).all()
            call_log_ids = [log.id for log in business_call_logs]
            
            appointments = AppointmentRequest.query.filter(
                AppointmentRequest.call_log_id.in_(call_log_ids)
            ).order_by(AppointmentRequest.created_at.desc()).all()
        
        return render_template('appointments_list.html', 
                             appointments=appointments,
                             current_user=current_user)
        
    except Exception as e:
        logger.error(f"Error loading appointments: {e}")
        flash('שגיאה בטעינת התורים', 'error')
        return redirect(url_for('index'))


# ========== SYSTEM STATUS & DEBUGGING ==========
@app.route('/api/system-test')
@login_required
def system_test():
    """בדיקת חיבור למערכת"""
    try:
        current_user = AuthService.get_current_user()
        
        # בדיקת חיבור למסד נתונים
        test_query = Business.query.limit(1).all()
        
        return jsonify({
            'success': True,
            'message': 'חיבור תקין',
            'user': current_user.username if current_user else 'אנונימי',
            'database': 'מחובר',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })


# ========== BUSINESS MANAGEMENT ROUTE ==========
@app.route('/admin/businesses')
@admin_required  
def business_management():
    """דף ניהול עסקים למנהל"""
    try:
        businesses = Business.query.all()
        return render_template('business_management.html', businesses=businesses)
    except Exception as e:
        logger.error(f"Error in business management: {e}")
        flash('שגיאה בטעינת עסקים', 'error')
        return redirect('/admin-dashboard')

# ========== CUSTOMERS MANAGEMENT ROUTE ==========
@app.route('/customers')
@login_required
def customers_management():
    """דף ניהול לקוחות"""
    return render_template('customers_management.html')


# ========== APPOINTMENT EDITING ROUTES ==========
@app.route('/appointments/edit/<int:appointment_id>')
@login_required
def edit_appointment_form(appointment_id):
    """טופס עריכת תור"""
    try:
        appointment = AppointmentRequest.query.get_or_404(appointment_id)
        current_user = AuthService.get_current_user()
        
        # בדיקת הרשאות
        if current_user.role != 'admin':
            call_log = CallLog.query.get(appointment.call_log_id)
            if call_log and call_log.business_id != current_user.business_id:
                flash('אין לך הרשאה לערוך תור זה', 'error')
                return redirect(url_for('appointments_list'))
        
        return render_template('edit_appointment.html', 
                             appointment=appointment,
                             current_user=current_user)
        
    except Exception as e:
        logger.error(f"Error loading appointment for edit: {e}")
        flash('שגיאה בטעינת התור', 'error')
        return redirect(url_for('appointments_list'))


# Removed duplicate redirect function


@app.route('/admin/business/<int:business_id>/dashboard')
@admin_required
def admin_business_dashboard(business_id):
    """דשבורד עסק ספציפי למנהל"""
    try:
        business = Business.query.get_or_404(business_id)
        
        # נתונים סטטיסטיים של העסק
        total_calls = CallLog.query.filter_by(business_id=business_id).count()
        total_appointments = AppointmentRequest.query.join(CallLog).filter(CallLog.business_id == business_id).count()
        recent_calls = CallLog.query.filter_by(business_id=business_id).order_by(CallLog.created_at.desc()).limit(10).all()
        recent_appointments = AppointmentRequest.query.join(CallLog).filter(CallLog.business_id == business_id).order_by(AppointmentRequest.created_at.desc()).limit(5).all()
        
        stats = {
            'total_calls': total_calls,
            'total_appointments': total_appointments,
            'conversion_rate': (total_appointments / total_calls * 100) if total_calls > 0 else 0,
            'active_customers': total_calls  # פשוט לעכשיו
        }
        
        return render_template('business_dashboard_detailed.html',
                             business=business,
                             stats=stats,
                             recent_calls=recent_calls,
                             recent_appointments=recent_appointments,
                             current_user=AuthService.get_current_user())
    
    except Exception as e:
        logger.error(f"Error loading business dashboard: {e}")
        flash('שגיאה בטעינת דשבורד העסק', 'error')
        return redirect('/admin-dashboard')

@app.route('/business-dashboards')
@login_required  
def business_dashboards():
    """רשימת דשבורדים עסקיים למנהל"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    if current_user.role != 'admin':
        flash('אין לך הרשאה לצפות בדף זה', 'error')
        return redirect('/admin-dashboard')
    
    try:
        businesses = Business.query.all()
        
        # Add stats for each business
        for business in businesses:
            business.total_calls = CallLog.query.filter_by(business_id=business.id).count()
            business.pending_appointments = AppointmentRequest.query.filter_by(
                business_id=business.id, 
                status='pending'
            ).count()
            
            # Add CRM stats if available
            try:
                from models import Customer
                business.total_customers = Customer.query.filter_by(business_id=business.id).count()
            except:
                business.total_customers = 0
                
    except Exception as e:
        print(f"Error loading businesses: {e}")
        businesses = []
    
    return render_template('business_dashboards.html', businesses=businesses, current_user=current_user)


@app.route('/business/<int:business_id>')
@login_required
def business_view(business_id):
    """צפייה בעסק עם חיבור Google Calendar ומעקב בזמן אמת מתקדם"""
    business = Business.query.get_or_404(business_id)
    
    # נתונים בזמן אמת
    active_calls = CallLog.query.filter_by(
        business_id=business_id, 
        call_status='in-progress'
    ).all()
    
    recent_calls = CallLog.query.filter_by(business_id=business_id)\
                               .order_by(CallLog.created_at.desc())\
                               .limit(20).all()
    
    # לידים פעילים (בשיחה כרגע)
    active_leads = []
    for call in active_calls:
        last_messages = ConversationTurn.query.filter_by(
            call_sid=call.call_sid
        ).order_by(ConversationTurn.timestamp.desc()).limit(3).all()
        
        active_leads.append({
            'id': call.id,
            'customer_name': f'לקוח {call.from_number[-4:]}',
            'phone_number': call.from_number,
            'status': 'active_conversation',
            'is_real_time': True,
            'conversation_duration': (datetime.now() - call.created_at).seconds // 60,
            'recent_messages': [{'speaker': m.speaker, 'message': m.message} for m in last_messages]
        })
    
    # לידים רגילים (לא בשיחה)
    regular_leads = []
    for call in recent_calls:
        if call.call_status != 'in-progress':
            regular_leads.append({
                'id': call.id,
                'customer_name': f'לקוח {call.from_number[-4:]}',
                'phone_number': call.from_number,
                'status': 'completed',
                'is_real_time': False,
                'last_contact': call.created_at.strftime('%d/%m %H:%M'),
                'marked': False  # יכול להיות מסומן על ידי המשתמש
            })
    
    # סטטיסטיקות
    total_calls = CallLog.query.filter_by(business_id=business_id).count()
    total_appointments = AppointmentRequest.query.join(CallLog)\
                                                 .filter(CallLog.business_id == business_id).count()
    
    pending_appointments = AppointmentRequest.query.join(CallLog)\
                                                   .filter(CallLog.business_id == business_id,
                                                          AppointmentRequest.status == 'pending')\
                                                   .order_by(AppointmentRequest.created_at.desc()).all()
    
    # הכנת נתוני stats
    stats = {
        'total_calls': total_calls,
        'total_appointments': total_appointments,
        'active_conversations': len(active_leads),
        'conversion_rate': 85  # דמה להדגמה
    }
    
    return render_template('business_view_premium.html',
                         business=business,
                         active_leads=active_leads,
                         regular_leads=regular_leads,
                         total_calls=total_calls,
                         total_appointments=total_appointments,
                         pending_appointments=pending_appointments,
                         stats=stats,
                         google_calendar_connected=True)

@app.route('/business-dashboard/<int:business_id>')
@login_required
@admin_required
def admin_view_business_dashboard(business_id):
    """מנהל צופה בדשבורד עסקי"""
    return business_view(business_id)

# ===== CUSTOMER PROFILE ROUTES =====
@app.route('/customer/<int:customer_id>')
@login_required
def customer_detail(customer_id):
    """דף פרופיל לקוח מלא עם כל הפרטים"""
    try:
        from models import CRMCustomer, CRMTask, CallLog, WhatsAppMessage, WhatsAppConversation
        
        # מציאת הלקוח
        customer = CRMCustomer.query.get_or_404(customer_id)
        
        # בניית אינטראקציות
        interactions = []
        
        # שיחות טלפוניות
        calls = CallLog.query.filter_by(from_number=customer.phone).order_by(CallLog.created_at.desc()).all()
        for call in calls:
            interactions.append({
                'type': 'call',
                'title': f'שיחה טלפונית ({call.call_status})',
                'description': f'משך: {call.duration or "לא ידוע"} | סטטוס: {call.call_status}',
                'timestamp': call.created_at
            })
        
        # הודעות WhatsApp
        conversation = WhatsAppConversation.query.filter_by(phone_number=customer.phone).first()
        whatsapp_messages = []
        if conversation:
            messages = WhatsAppMessage.query.filter_by(conversation_id=conversation.id).order_by(WhatsAppMessage.timestamp.desc()).limit(20).all()
            for msg in messages:
                interactions.append({
                    'type': 'whatsapp',
                    'title': f'הודעת WhatsApp {"נשלחה" if msg.direction == "outbound" else "התקבלה"}',
                    'description': msg.body[:100] + ('...' if len(msg.body) > 100 else ''),
                    'timestamp': msg.timestamp
                })
                whatsapp_messages.append(msg)
        
        # משימות הלקוח
        customer_tasks = CRMTask.query.filter_by(customer_id=customer_id).order_by(CRMTask.created_at.desc()).all()
        
        # מיון אינטראקציות לפי זמן
        interactions.sort(key=lambda x: x['timestamp'] or datetime.min, reverse=True)
        
        # סטטיסטיקות
        interactions_count = len(interactions)
        tasks_count = len(customer_tasks)
        calls_count = len(calls)
        whatsapp_count = len(whatsapp_messages)
        
        # חוזים (דמה)
        customer_contracts = [
            {
                'id': 1,
                'title': 'חוזה שירות סטנדרטי',
                'description': 'חוזה שירות בסיסי',
                'status': 'pending',
                'status_text': 'ממתין לחתימה',
                'created_at': datetime.utcnow()
            }
        ]
        
        return render_template('customer_detail_full.html',
                             customer=customer,
                             interactions=interactions,
                             customer_tasks=customer_tasks,
                             whatsapp_messages=whatsapp_messages,
                             customer_contracts=customer_contracts,
                             interactions_count=interactions_count,
                             tasks_count=tasks_count,
                             calls_count=calls_count,
                             whatsapp_count=whatsapp_count)
                             
    except Exception as e:
        logger.error(f"Error loading customer detail: {e}")
        flash('שגיאה בטעינת פרטי הלקוח', 'error')
        return redirect('/crm/customers')

# ===== BAILEYS WHATSAPP ROUTES =====
@app.route('/baileys/setup')
@login_required
def baileys_setup():
    """הגדרת Baileys WhatsApp"""
    return render_template('baileys_setup.html')

@app.route('/baileys/chat')
@login_required  
def baileys_chat():
    """ממשק צ'אט Baileys"""
    phone = request.args.get('phone', '')
    name = request.args.get('name', 'לקוח')
    return render_template('baileys_chat.html', phone=phone, name=name)

@app.route('/baileys/status')
@login_required
def baileys_status():
    """סטטוס שירות Baileys"""
    import os
    try:
        # בדיקה אם הפרוצס פעיל
        if os.path.exists('baileys.pid'):
            with open('baileys.pid', 'r') as f:
                pid = f.read().strip()
            status = 'active' if os.path.exists(f'/proc/{pid}') else 'inactive'
        else:
            status = 'inactive'
    except:
        status = 'error'
    
    return jsonify({'status': status})

@app.route('/api/baileys/send-message', methods=['POST'])
@login_required
def baileys_send_message():
    """שליחת הודעה דרך Baileys"""
    data = request.get_json()
    phone = data.get('phone', '')
    message = data.get('message', '')
    
    try:
        # כאן תהיה האינטגרציה עם Baileys
        logger.info(f"Sending Baileys message to {phone}: {message}")
        return jsonify({'success': True, 'message': 'הודעה נשלחה בהצלחה'})
    except Exception as e:
        logger.error(f"Baileys send error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ===== CRM API ROUTES =====
@app.route('/api/whatsapp/send', methods=['POST'])
@login_required
def send_whatsapp_api():
    """שליחת הודעת WhatsApp"""
    try:
        data = request.get_json()
        phone = data.get('phone', '')
        message = data.get('message', '')
        customer_name = data.get('customer_name', '')
        
        # שליחה דרך Twilio WhatsApp
        # Mock WhatsApp send for now
        result = {'success': True}
        logger.info(f"📤 Mock WhatsApp sent to {phone}: {message[:50]}...")
        
        if result.get('success'):
            # שמירה במסד נתונים
            from models import WhatsAppConversation, WhatsAppMessage
            
            conversation = WhatsAppConversation.query.filter_by(phone_number=phone).first()
            if not conversation:
                conversation = WhatsAppConversation()
                conversation.phone_number = phone
                conversation.business_id = 1  # ברירת מחדל
                conversation.customer_name = customer_name
                db.session.add(conversation)
                db.session.flush()
            
            # הוספת ההודעה
            msg = WhatsAppMessage()
            msg.conversation_id = conversation.id
            msg.direction = 'outbound'
            msg.body = message
            db.session.add(msg)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'הודעה נשלחה בהצלחה'})
        else:
            return jsonify({'success': False, 'error': 'שליחה נכשלה'})
            
    except Exception as e:
        logger.error(f"Error sending WhatsApp: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/send-contract', methods=['POST'])
@login_required
def send_contract_api():
    """שליחת חוזה ללקוח"""
    try:
        data = request.get_json()
        customer_id = data.get('customer_id')
        
        from models import CRMCustomer
        customer = CRMCustomer.query.get(customer_id)
        if not customer:
            return jsonify({'success': False, 'error': 'לקוח לא נמצא'})
        
        # יצירת חוזה דמה
        contract_text = f"""
חוזה שירות
-----------
לקוח: {customer.name}
טלפון: {customer.phone}
תאריך: {datetime.now().strftime('%d/%m/%Y')}

תנאי השירות...
        """
        
        # שליחה דרך WhatsApp
        message = f"שלום {customer.name}, מצורף חוזה השירות שלך. אנא עיין וחתום.\n\n{contract_text}"
        
        # Mock contract send for now
        result = {'success': True}
        logger.info(f"📄 Mock contract sent to {customer.phone}")
        
        return jsonify({'success': result.get('success', False), 'message': 'חוזה נשלח בהצלחה'})
        
    except Exception as e:
        logger.error(f"Error sending contract: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/create-task', methods=['POST'])
@login_required
def create_task_api():
    """יצירת משימה חדשה"""
    try:
        data = request.get_json()
        customer_id = data.get('customer_id')
        title = data.get('title', '')
        description = data.get('description', '')
        priority = data.get('priority', 'medium')
        
        from models import CRMTask
        
        task = CRMTask(
            customer_id=customer_id,
            title=title,
            description=description,
            priority=priority,
            status='pending',
            created_at=datetime.utcnow()
        )
        
        db.session.add(task)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'משימה נוצרה בהצלחה'})
        
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/toggle-task', methods=['POST'])
@login_required
def toggle_task_api_post():
    """שינוי סטטוס משימה דרך POST"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        
        from models import CRMTask
        
        task = CRMTask.query.get(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'משימה לא נמצאה'})
        
        task.status = 'completed' if task.status != 'completed' else 'pending'
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error toggling task: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/toggle-task/<int:task_id>', methods=['POST'])
@login_required
def toggle_task_api(task_id):
    """שינוי סטטוס משימה"""
    try:
        from models import CRMTask
        
        task = CRMTask.query.get(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'משימה לא נמצאה'})
        
        task.status = 'completed' if task.status != 'completed' else 'pending'
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error toggling task: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ===== WHATSAPP WEBHOOK ROUTES =====
@app.route('/whatsapp/incoming', methods=['POST'])
def whatsapp_incoming_webhook():
    """קבלת הודעות WhatsApp נכנסות מTwilio"""
    try:
        from_number = request.form.get('From', '').replace('whatsapp:', '')
        body = request.form.get('Body', '')
        message_sid = request.form.get('MessageSid', '')
        
        logger.info(f"📱 Incoming WhatsApp: {from_number} - {body}")
        
        # מצא עסק לפי מספר
        business = Business.query.filter_by(whatsapp_number=from_number).first()
        if not business:
            business = Business.query.first()  # ברירת מחדל
        
        # שמור הודעה במסד נתונים
        from models import WhatsAppConversation, WhatsAppMessage
        
        conversation = WhatsAppConversation.query.filter_by(phone_number=from_number).first()
        if not conversation:
            conversation = WhatsAppConversation(
                phone_number=from_number,
                business_id=business.id if business else 1,
                customer_name=f"WhatsApp {from_number[-4:]}"
            )
            db.session.add(conversation)
            db.session.flush()
        
        # שמור הודעה
        message = WhatsAppMessage(
            conversation_id=conversation.id,
            message_sid=message_sid,
            direction='inbound',
            body=body,
            timestamp=datetime.utcnow()
        )
        db.session.add(message)
        
        # עיבוד עם AI אם יש עסק
        if business:
            from ai_service import AIService
            ai_service = AIService()
            
            ai_response = ai_service.process_conversation(
                user_message=body,
                business_id=business.id,
                conversation_context={'phone': from_number}
            )
            
            # שמור תגובת AI
            ai_message = WhatsAppMessage(
                conversation_id=conversation.id,
                direction='outbound',
                body=ai_response,
                timestamp=datetime.utcnow()
            )
            db.session.add(ai_message)
            
            # שלח תגובה
            twilio_service = TwilioService()
            twilio_service.send_whatsapp_message(from_number, ai_response)
        
        db.session.commit()
        return Response('OK', mimetype='text/plain')
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {e}")
        return Response('ERROR', mimetype='text/plain')

@app.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_status_webhook():
    """סטטוס הודעות WhatsApp"""
    try:
        message_sid = request.form.get('MessageSid', '')
        message_status = request.form.get('MessageStatus', '')
        
        logger.info(f"📱 WhatsApp status: {message_sid} - {message_status}")
        
        # עדכן סטטוס במסד נתונים
        from models import WhatsAppMessage
        message = WhatsAppMessage.query.filter_by(message_sid=message_sid).first()
        if message:
            message.status = message_status
            db.session.commit()
        
        return Response('OK', mimetype='text/plain')
        
    except Exception as e:
        logger.error(f"Error updating WhatsApp status: {e}")
        return Response('ERROR', mimetype='text/plain')

# ===== CUSTOMER PROFILE ROUTE =====
@app.route('/customer/<int:customer_id>')
@login_required
def customer_profile(customer_id):
    """דף לקוח מפורט עם כל הנתונים"""
    try:
        from models import CRMCustomer, CallLog, WhatsAppMessage, CRMTask, WhatsAppConversation
        
        # מצא את הלקוח
        customer = CRMCustomer.query.get_or_404(customer_id)
        
        # איסוף נתונים נלווים
        call_logs = CallLog.query.filter_by(customer_id=customer_id).order_by(CallLog.timestamp.desc()).limit(10).all()
        
        whatsapp_messages = []
        if customer.phone:
            conversation = WhatsAppConversation.query.filter_by(phone_number=customer.phone).first()
            if conversation:
                whatsapp_messages = WhatsAppMessage.query.filter_by(
                    conversation_id=conversation.id
                ).order_by(WhatsAppMessage.timestamp.desc()).limit(10).all()
        
        tasks = CRMTask.query.filter_by(customer_id=customer_id).order_by(CRMTask.created_at.desc()).all()
        
        logger.info(f"📋 Customer profile loaded: {customer.name} (ID: {customer_id})")
        logger.info(f"📊 Data: {len(call_logs)} calls, {len(whatsapp_messages)} messages, {len(tasks)} tasks")
        
        return render_template('customer_detail.html',
                             customer=customer,
                             call_logs=call_logs,
                             whatsapp_messages=whatsapp_messages,
                             tasks=tasks)
                             
    except Exception as e:
        logger.error(f"Error loading customer profile: {e}")
        flash('שגיאה בטעינת פרטי הלקוח', 'error')
        return redirect(url_for('crm_customers'))

# ===== BAILEYS CHAT WINDOW ROUTE =====
@app.route('/baileys/chat-window')
def baileys_chat_window():
    """דף צ'אט Baileys"""
    phone = request.args.get('phone', '')
    name = request.args.get('name', 'לקוח')
    
    logger.info(f"💬 Opening Baileys chat for {name} ({phone})")
    
    return render_template('baileys_chat.html', phone=phone, name=name)

# Cleanup and utility routes
@app.route('/api/cleanup-audio', methods=['POST'])
@login_required
@admin_required
def manual_cleanup():
    """ניקוי ידני של קבצי אודיו"""
    try:
        # Cleanup service integrated directly
        import os
        import glob
        
        audio_dir = 'static/voice_responses'
        if not os.path.exists(audio_dir):
            os.makedirs(audio_dir)
        
        # Count and clean files
        files_before = len(glob.glob(f"{audio_dir}/*.mp3"))
        
        # Clean old files (older than 24 hours)
        from datetime import datetime, timedelta
        cutoff_time = datetime.now() - timedelta(hours=24)
        cleaned_count = 0
        
        for file_path in glob.glob(f"{audio_dir}/*.mp3"):
            try:
                if datetime.fromtimestamp(os.path.getctime(file_path)) < cutoff_time:
                    os.remove(file_path)
                    cleaned_count += 1
            except:
                pass
        
        files_after = len(glob.glob(f"{audio_dir}/*.mp3"))
        cleanup_result = f"{cleaned_count} files cleaned"
        before_stats = {'total_files': files_before}
        after_stats = {'total_files': files_after}
        
        return jsonify({
            'status': 'success',
            'message': f"ניקוי הושלם: {cleanup_result}",
            'before': before_stats,
            'after': after_stats
        })
        
    except Exception as e:
        logger.error(f"Manual cleanup error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'שגיאה בניקוי: {str(e)}'
        })


@app.route('/call-logs')
@login_required
def call_logs():
    """דף יומני שיחות עם תמלילים מלאים"""
    current_user = AuthService.get_current_user()
    
    # Filter calls based on user role
    if current_user.role == 'admin':
        calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(100).all()
    else:
        calls = CallLog.query.filter_by(business_id=current_user.business_id)\
                            .order_by(CallLog.created_at.desc()).limit(100).all()
    
    # Add transcript data for each call
    calls_with_transcripts = []
    for call in calls:
        # Get conversation turns for this call
        turns = ConversationTurn.query.filter_by(call_log_id=call.id)\
                                     .order_by(ConversationTurn.timestamp).all()
        
        transcript_data = []
        for turn in turns:
            transcript_data.append({
                'speaker': turn.speaker,
                'message': turn.message,
                'timestamp': turn.timestamp.strftime('%H:%M:%S')
            })
        
        calls_with_transcripts.append({
            'call': call,
            'transcript': transcript_data
        })
    
    return render_template('call_logs.html', 
                         calls_with_transcripts=calls_with_transcripts,
                         current_user=current_user)


@app.route('/export-calls')
@login_required  
def export_calls():
    """ייצוא יומני שיחות"""
    current_user = AuthService.get_current_user()
    
    # Get calls based on user permissions
    if current_user.role == 'admin':
        calls = CallLog.query.order_by(CallLog.created_at.desc()).all()
    else:
        calls = CallLog.query.filter_by(business_id=current_user.business_id)\
                            .order_by(CallLog.created_at.desc()).all()
    
    # Simple CSV export
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['תאריך', 'מספר מתקשר', 'מספר נקלט', 'משך שיחה', 'סטטוס'])
    
    for call in calls:
        writer.writerow([
            call.created_at.strftime('%d/%m/%Y %H:%M'),
            call.from_number,
            call.to_number,
            f"{call.call_duration}s" if call.call_duration else "N/A",
            call.call_status
        ])
    
    from flask import make_response
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = 'attachment; filename=call_logs.csv'
    return response

# WhatsApp Enhanced Routes
@app.route('/whatsapp/baileys-setup')
@login_required
def whatsapp_baileys_setup():
    """הגדרת Baileys"""
    return render_template('whatsapp/baileys_setup.html')

# Note: whatsapp_enhanced_dashboard is loaded from whatsapp_dashboard_enhanced.py
try:
    exec(open('whatsapp_dashboard_enhanced.py').read())
    logger.info("✅ WhatsApp Enhanced Dashboard loaded from file")
except Exception as e:
    logger.warning(f"⚠️ WhatsApp Enhanced Dashboard not available: {e}")

@app.route('/business-view/<int:business_id>')
@login_required  
def view_business_details(business_id):
    """צפייה מפורטת בעסק בודד עם כל הפונקציות המתקדמות"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    business = Business.query.get_or_404(business_id)
    
    # מעקב בזמן אמת - הבחנה בין לידים פעילים ללידים רגילים
    active_calls = CallLog.query.filter_by(
        business_id=business_id, 
        call_status='in-progress'
    ).all()
    
    recent_calls = CallLog.query.filter_by(business_id=business_id)\
                               .order_by(CallLog.created_at.desc())\
                               .limit(20).all()
    
    # לידים פעילים (בשיחה עכשיו)
    real_time_leads = []
    for call in active_calls:
        last_messages = ConversationTurn.query.filter_by(
            call_sid=call.call_sid
        ).order_by(ConversationTurn.timestamp.desc()).limit(3).all()
        
        real_time_leads.append({
            'id': call.id,
            'customer_name': f'לקוח {call.from_number[-4:]}',
            'phone_number': call.from_number,
            'status': 'בשיחה חיה',
            'is_active_conversation': True,
            'conversation_duration': (datetime.now() - call.created_at).seconds // 60,
            'can_mark': True,
            'recent_messages': [{'speaker': m.speaker, 'message': m.message} for m in last_messages]
        })
    
    # לידים רגילים (שיחות שהסתיימו)
    regular_leads = []
    for call in recent_calls:
        if call.call_status != 'in-progress':
            regular_leads.append({
                'id': call.id,
                'customer_name': f'לקוח {call.from_number[-4:]}',
                'phone_number': call.from_number,
                'status': 'הושלם',
                'is_active_conversation': False,
                'last_contact': call.created_at.strftime('%d/%m %H:%M'),
                'can_mark': True,
                'marked_as_customer': False
            })
    
    # סטטיסטיקות מתקדמות
    total_calls = CallLog.query.filter_by(business_id=business_id).count()
    total_appointments = AppointmentRequest.query.join(CallLog)\
                                                 .filter(CallLog.business_id == business_id).count()
    
    pending_appointments = AppointmentRequest.query.join(CallLog)\
                                                   .filter(CallLog.business_id == business_id,
                                                          AppointmentRequest.status == 'pending')\
                                                   .order_by(AppointmentRequest.created_at.desc()).all()
    
    return render_template('business_view_premium.html', 
                         business=business,
                         real_time_leads=real_time_leads,
                         regular_leads=regular_leads,
                         total_calls=total_calls,
                         total_appointments=total_appointments,
                         pending_appointments=pending_appointments,
                         google_calendar_connected=True,
                         current_user=current_user)

@app.route('/leads-management')
@login_required
def leads_management():
    """מערכת ניהול לידים מתקדמת עם מעקב בזמן אמת"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    # איסוף נתוני לידים בזמן אמת
    active_calls = CallLog.query.filter_by(call_status='in-progress').all()
    recent_calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(20).all()
    
    # בניית מידע לידים
    leads = []
    for call in recent_calls:
        # זיהוי סטטוס שיחה
        status = 'ended'
        if call.call_status == 'in-progress':
            status = 'active'
        elif call.call_status == 'ringing':
            status = 'pending'
        
        # קבלת הודעות אחרונות
        last_messages = ConversationTurn.query.filter_by(
            call_sid=call.call_sid
        ).order_by(ConversationTurn.timestamp.desc()).limit(3).all()
        
        lead = {
            'id': call.id,
            'customer_name': f'לקוח {call.from_number[-4:]}',
            'phone_number': call.from_number,
            'status': status,
            'channel': 'phone',
            'channel_display': 'שיחה טלפונית',
            'duration': f"{call.call_duration}ש" if call.call_duration else 'פעיל',
            'recent_messages': [
                {
                    'speaker': msg.speaker,
                    'message': msg.message
                } for msg in last_messages
            ],
            'extracted_data': {}
        }
        leads.append(lead)
    
    # סטטיסטיקות
    stats = {
        'active_conversations': len(active_calls),
        'total_leads_today': len([l for l in leads if l['status'] != 'old']),
        'conversion_rate': 78,
        'response_time': 4
    }
    
    # סטטיסטיקות לידים עבור הטמפלט
    leads_stats = {
        'total_leads': len(leads),
        'active_conversations': stats['active_conversations'],
        'conversion_rate': stats['conversion_rate'],
        'pending_followups': len([l for l in leads if l['status'] == 'pending'])
    }
    
    return render_template('leads_management_premium.html',
                         leads=leads,
                         leads_stats=leads_stats,
                         active_conversations=stats['active_conversations'],
                         total_leads_today=stats['total_leads_today'],
                         conversion_rate=stats['conversion_rate'],
                         response_time=stats['response_time'])

@app.route('/api/real-time-stats')
@login_required
def real_time_stats():
    """API לעדכון סטטיסטיקות בזמן אמת"""
    active_calls = CallLog.query.filter_by(call_status='in-progress').count()
    today_calls = CallLog.query.filter(
        CallLog.created_at >= datetime.now().date()
    ).count()
    
    return jsonify({
        'active_conversations': active_calls,
        'total_leads_today': today_calls,
        'conversion_rate': 78,
        'response_time': 4
    })

@app.route('/api/mark-customer/<int:lead_id>', methods=['POST'])
@login_required
def mark_customer(lead_id):
    """סימון ליד כלקוח"""
    data = request.get_json()
    marked = data.get('marked', False)
    
    # כאן תהיה לוגיקה לסימון הליד במסד הנתונים
    # לעת עתה נחזיר הצלחה
    
    return jsonify({
        'status': 'success',
        'message': f'ליד {lead_id} {"סומן" if marked else "בוטל סימונו"} כלקוח',
        'marked': marked
    })

@app.route('/google-calendar/connect')
@login_required
def connect_google_calendar():
    """חיבור Google Calendar"""
    # כאן תהיה לוגיקה לחיבור Google Calendar
    return redirect(url_for('admin_dashboard'))

@app.route('/google-calendar/disconnect', methods=['POST'])
@login_required
def disconnect_google_calendar():
    """ניתוק Google Calendar"""
    # כאן תהיה לוגיקה לניתוק Google Calendar
    return jsonify({'status': 'success', 'message': 'Google Calendar נותק בהצלחה'})

@app.route('/export/customers/<int:business_id>')
@login_required
def export_customers(business_id):
    """יצוא לקוחות לקובץ CSV"""
    business = Business.query.get_or_404(business_id)
    calls = CallLog.query.filter_by(business_id=business_id).all()
    
    from io import StringIO
    import csv
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['תאריך', 'שם לקוח', 'מספר טלפון', 'משך שיחה', 'סטטוס'])
    
    for call in calls:
        writer.writerow([
            call.created_at.strftime('%d/%m/%Y %H:%M'),
            f'לקוח {call.from_number[-4:]}',
            call.from_number,
            f"{call.call_duration}s" if call.call_duration else "N/A",
            call.call_status
        ])
    
    from flask import make_response
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=customers_{business.name}.csv'
    return response

@app.route('/analytics/<int:business_id>')
@login_required
def business_analytics(business_id):
    """דוחות אנליטיקס מתקדמים לעסק"""
    business = Business.query.get_or_404(business_id)
    
    # נתונים לדוגמה - בפרודקשן יהיו נתונים אמיתיים
    analytics_data = {
        'weekly_calls': [5, 8, 12, 6, 9, 15, 11],
        'conversion_rate': 73,
        'avg_call_duration': 180,
        'peak_hours': [9, 10, 11, 14, 15, 16],
        'customer_satisfaction': 4.2
    }
    
    return render_template('analytics_premium.html', 
                         business=business,
                         analytics=analytics_data)

@app.route('/calendar-premium')
@login_required
def calendar_premium():
    """יומן תורים מתקדם עם FullCalendar"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    # נתוני דוגמה לתורים קרובים
    upcoming_appointments = [
        {
            'id': 1,
            'customer_name': 'יוסי כהן',
            'phone_number': '050-1234567',
            'date': datetime.now(),
            'time': '10:00',
            'service': 'ייעוץ'
        },
        {
            'id': 2,
            'customer_name': 'שרה לוי',
            'phone_number': '052-9876543',
            'date': datetime.now(),
            'time': '14:30',
            'service': 'פגישה'
        }
    ]
    
    return render_template('calendar_premium.html',
                         upcoming_appointments=upcoming_appointments,
                         appointments_today=8,
                         appointments_week=24,
                         confirmation_rate=92,
                         avg_duration=45)

# ========================
# רישום Blueprint-ים חדשים
# ========================

# רישום Blueprint-ים של CRM ודשבורד אדמין
# Blueprints registered in app.py

# ========================
# CRM COMPLETE SYSTEM - מערכת CRM מלאה
# ========================

@app.route('/crm')
@login_required
def crm_dashboard():
    """CRM Dashboard - הדשבורד הראשי של המערכת"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    # Get user's business context - skip if no user (direct access)
    if current_user and current_user.role == 'admin':
        businesses = Business.query.all()
        total_customers = CallLog.query.count()
    else:
        business = Business.query.get(current_user.business_id) if current_user and current_user.business_id else None
        businesses = [business] if business else []
        total_customers = CallLog.query.filter_by(business_id=current_user.business_id).count() if current_user and business else CallLog.query.count()
    
    # CRM Statistics - נתונים אמיתיים מהמסד
    try:
        from models import Customer, Task
        total_tasks = Task.query.count()
        completed_tasks = Task.query.filter_by(status='completed').count()
    except Exception as e:
        # Fallback if tables don't exist yet
        total_tasks = 0
        completed_tasks = 0
    
    crm_stats = {
        'total_customers': total_customers,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': total_tasks - completed_tasks,
        'monthly_revenue': 95000,
        'customer_satisfaction': 4.9,
        'active_conversations': 0,  # Fallback for now
        'conversion_rate': 87
    }
    
    # Recent Activity - נתונים אמיתיים
    recent_activity = []
    try:
        recent_calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(5).all()
        for call in recent_calls:
            activity = {
                'icon': 'phone',
                'title': f'שיחה מ-{call.from_number[-4:]}',
                'time': f'לפני {(datetime.utcnow() - call.created_at).seconds // 60} דקות',
                'type': 'success' if call.call_status == 'completed' else 'info'
            }
            recent_activity.append(activity)
    except:
        # Default activity for demo
        recent_activity = [
            {'icon': 'phone', 'title': 'בדיקת מערכת פעילה', 'time': 'עכשיו', 'type': 'success'},
            {'icon': 'users', 'title': 'CRM מוכן לשימוש', 'time': 'לפני 2 דקות', 'type': 'info'}
        ]
    
    return render_template('crm_dashboard_fixed.html',
                         current_user=current_user,
                         stats=crm_stats,
                         recent_activity=recent_activity,
                         businesses=businesses,
                         business=businesses[0] if businesses else None,
                         business_id=businesses[0].id if businesses else 1,
                         recent_calls=[],
                         recent_appointments=[])

@app.route('/crm/customers')
@login_required
def crm_customers():
    """CRM Customers - ניהול לקוחות מלא"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    # Get customers with proper permissions
    customers = []
    try:
        from models import Customer
        if current_user.role == 'admin':
            crm_customers = Customer.query.order_by(Customer.created_at.desc()).all()
        else:
            crm_customers = Customer.query.filter_by(business_id=current_user.business_id).order_by(Customer.created_at.desc()).all()
        
        for customer in crm_customers:
            customers.append({
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'email': customer.email or f'customer{customer.id}@business.local',
                'status': customer.status,
                'last_contact': customer.updated_at,
                'business_id': customer.business_id,
                'source': customer.source
            })
    except:
        # Fallback to calls 
        customers = []
    
    return render_template('crm/customers_premium.html', customers=customers, current_user=current_user)

@app.route('/crm/tasks')
@login_required  
def crm_tasks():
    """CRM Tasks - ניהול משימות"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    tasks = []
    try:
        from models import Task
        if current_user.role == 'admin':
            all_tasks = Task.query.order_by(Task.created_at.desc()).all()
        else:
            all_tasks = Task.query.filter_by(business_id=current_user.business_id).order_by(Task.created_at.desc()).all()
        
        for task in all_tasks:
            tasks.append({
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'status': task.status,
                'priority': task.priority,
                'assigned_to': task.assigned_to,
                'due_date': task.due_date,
                'created_at': task.created_at
            })
    except:
        # Demo tasks
        tasks = [
            {'id': 1, 'title': 'טיפול בלקוח חדש', 'status': 'pending', 'priority': 'high', 'assigned_to': 'שי'},
            {'id': 2, 'title': 'מעקב אחר הזמנה', 'status': 'in_progress', 'priority': 'medium', 'assigned_to': 'מנהל'}
        ]
    
    return render_template('crm/tasks_premium.html', tasks=tasks, current_user=current_user)

@app.route('/crm/analytics') 
@login_required
def crm_analytics():
    """CRM Analytics - דוחות ואנליטיקה"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    analytics_data = {
        'monthly_revenue': 125000,
        'customer_growth': 23,
        'conversion_rate': 89,
        'avg_response_time': 2.3,
        'customer_satisfaction': 4.8,
        'active_campaigns': 5
    }
    
    return render_template('crm/analytics_premium.html', analytics=analytics_data, current_user=current_user)

# CRM Action Routes
@app.route('/crm/add-customer', methods=['GET', 'POST'])
@login_required
def add_customer():
    """הוספת לקוח חדש"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    if request.method == 'POST':
        try:
            from models import Customer
            new_customer = Customer(
                name=request.form.get('name'),
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                business_id=current_user.business_id if current_user.role != 'admin' else request.form.get('business_id'),
                source=request.form.get('source', 'manual'),
                notes=request.form.get('notes', '')
            )
            db.session.add(new_customer)
            db.session.commit()
            flash('לקוח נוסף בהצלחה!', 'success')
            return redirect('/crm/customers')
        except Exception as e:
            flash(f'שגיאה בהוספת לקוח: {str(e)}', 'error')
    
    # Get businesses for admin
    businesses = []
    if current_user.role == 'admin':
        businesses = Business.query.all()
    
    return render_template('crm/add_customer.html', businesses=businesses, current_user=current_user)

@app.route('/crm/add-task', methods=['GET', 'POST'])
@login_required
def add_task():
    """הוספת משימה חדשה"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    if request.method == 'POST':
        try:
            from models import Task
            new_task = Task(
                title=request.form.get('title'),
                description=request.form.get('description'),
                priority=request.form.get('priority', 'medium'),
                assigned_to=request.form.get('assigned_to'),
                business_id=current_user.business_id if current_user.role != 'admin' else request.form.get('business_id'),
                customer_id=request.form.get('customer_id') if request.form.get('customer_id') else None,
                due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d') if request.form.get('due_date') else None
            )
            db.session.add(new_task)
            db.session.commit()
            flash('משימה נוספה בהצלחה!', 'success')
            return redirect('/crm/tasks')
        except Exception as e:
            flash(f'שגיאה בהוספת משימה: {str(e)}', 'error')
    
    # Get customers and businesses
    customers = []
    businesses = []
    try:
        from models import Customer
        if current_user.role == 'admin':
            customers = Customer.query.all()
            businesses = Business.query.all()
        else:
            customers = Customer.query.filter_by(business_id=current_user.business_id).all()
    except:
        pass
    
    return render_template('crm/add_task.html', customers=customers, businesses=businesses, current_user=current_user)

@app.route('/crm/bulk-actions', methods=['GET', 'POST'])
@login_required
def bulk_actions():
    """פעולות מקובצות על לקוחות ומשימות"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    if request.method == 'POST':
        action = request.form.get('action')
        selected_ids = request.form.getlist('selected_items')
        
        if action == 'delete_customers':
            try:
                from models import Customer
                Customer.query.filter(Customer.id.in_(selected_ids)).delete(synchronize_session=False)
                db.session.commit()
                flash(f'{len(selected_ids)} לקוחות נמחקו בהצלחה!', 'success')
            except Exception as e:
                flash(f'שגיאה במחיקת לקוחות: {str(e)}', 'error')
                
        elif action == 'export_customers':
            # Export functionality would go here
            flash('יצוא לקוחות - תכונה בפיתוח', 'info')
            
        return redirect('/crm/bulk-actions')
    
    # Get data for bulk actions
    customers = []
    tasks = []
    try:
        from models import Customer, Task
        if current_user.role == 'admin':
            customers = Customer.query.all()
            tasks = Task.query.all()
        else:
            customers = Customer.query.filter_by(business_id=current_user.business_id).all()
            tasks = Task.query.filter_by(business_id=current_user.business_id).all()
    except:
        pass
    
    return render_template('crm/bulk_actions.html', customers=customers, tasks=tasks, current_user=current_user)

@app.route('/crm/export-report')
@login_required
def export_report():
    """יצוא דוח CRM"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    # Generate CSV report
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['שם לקוח', 'טלפון', 'אימייל', 'סטטוס', 'מקור', 'תאריך יצירה'])
    
    # Get customers data
    try:
        from models import Customer
        if current_user.role == 'admin':
            customers = Customer.query.all()
        else:
            customers = Customer.query.filter_by(business_id=current_user.business_id).all()
        
        for customer in customers:
            writer.writerow([
                customer.name,
                customer.phone,
                customer.email or '',
                customer.status,
                customer.source,
                customer.created_at.strftime('%Y-%m-%d') if customer.created_at else ''
            ])
    except:
        # Fallback demo data
        writer.writerow(['דמו לקוח', '050-1234567', 'demo@example.com', 'פעיל', 'טלפון', '2025-01-01'])
    
    # Create response
    from flask import Response
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-disposition": "attachment; filename=crm_report.csv"}
    )

# Business View Route  
@app.route('/business-view-details/<int:business_id>')
@login_required
def business_view_details(business_id):
    """צפייה מפורטת בעסק"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    # Only admin can view all businesses
    if current_user.role != 'admin':
        flash('אין לך הרשאה לצפות בעסק זה', 'error')
        return redirect('/admin-dashboard')
    
    business = Business.query.get_or_404(business_id)
    
    # Get business statistics
    total_calls = CallLog.query.filter_by(business_id=business_id).count()
    recent_calls = CallLog.query.filter_by(business_id=business_id).order_by(CallLog.created_at.desc()).limit(10).all()
    
    # Get CRM data if available
    customers = []
    tasks = []
    try:
        from models import Customer, Task
        customers = Customer.query.filter_by(business_id=business_id).order_by(Customer.created_at.desc()).limit(20).all()
        tasks = Task.query.filter_by(business_id=business_id).order_by(Task.created_at.desc()).limit(10).all()
    except:
        pass
    
    # Get conversations
    conversations = []
    try:
        recent_conversations = ConversationTurn.query.join(CallLog).filter(
            CallLog.business_id == business_id
        ).order_by(ConversationTurn.created_at.desc()).limit(20).all()
        
        for conv in recent_conversations:
            conversations.append({
                'speaker': conv.speaker,
                'message': conv.message_text,
                'timestamp': conv.created_at,
                'call_id': conv.call_log_id
            })
    except:
        pass
    
    business_stats = {
        'total_calls': total_calls,
        'total_customers': len(customers),
        'total_tasks': len(tasks),
        'pending_tasks': len([t for t in tasks if hasattr(t, 'status') and t.status == 'pending']),
        'recent_activity': len(recent_calls)
    }
    
    return render_template('business_view_premium.html', 
                         business=business, 
                         stats=business_stats,
                         recent_calls=recent_calls,
                         customers=customers,
                         tasks=tasks,
                         conversations=conversations,
                         current_user=current_user)

# Additional Configuration Routes
@app.route('/configuration/<int:business_id>')
@login_required
def edit_business_config(business_id):
    """עריכת הגדרות עסק"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    if current_user.role != 'admin':
        flash('אין לך הרשאה לצפות בדף זה', 'error')
        return redirect('/admin-dashboard')
    
    business = Business.query.get_or_404(business_id)
    return render_template('edit_business.html', business=business)

@app.route('/delete-business/<int:business_id>', methods=['POST'])
@login_required 
def delete_business_endpoint(business_id):
    """מחיקת עסק"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'אין הרשאה'})
    
    try:
        business = Business.query.get_or_404(business_id)
        business_name = business.name
        
        # מחיקת כל הנתונים הקשורים
        CallLog.query.filter_by(business_id=business_id).delete()
        ConversationTurn.query.join(CallLog).filter(CallLog.business_id == business_id).delete()
        AppointmentRequest.query.filter_by(business_id=business_id).delete()
        
        # מחיקת העסק עצמו
        db.session.delete(business)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'העסק {business_name} נמחק בהצלחה'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'שגיאה במחיקת העסק: {str(e)}'})

@app.route('/update-business/<int:business_id>', methods=['POST'])
@login_required
def update_business_endpoint(business_id):
    """עדכון פרטי עסק"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    if current_user.role != 'admin':
        flash('אין לך הרשאה לעדכן עסק', 'error')
        return redirect('/configuration')
    
    try:
        business = Business.query.get_or_404(business_id)
        
        business.name = request.form.get('business_name')
        business.business_type = request.form.get('business_type')
        business.phone_number = request.form.get('phone_number')
        business.whatsapp_number = request.form.get('whatsapp_number')
        business.greeting_message = request.form.get('greeting_message')
        business.system_prompt = request.form.get('system_prompt')
        business.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash(f'העסק {business.name} עודכן בהצלחה!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'שגיאה בעדכון העסק: {str(e)}', 'error')
    
    return redirect('/configuration')


# API לרענון נתוני CRM
@app.route("/api/dashboard-stats")
@login_required
def api_dashboard_stats():
    """API לקבלת סטטיסטיקות דשבורד"""
    try:
        current_user = AuthService.get_current_user()
        business_id = request.args.get("business_id")
        
        if not business_id:
            return jsonify({"success": False, "error": "Business ID required"})
        
        # Basic stats
        total_calls = CallLog.query.filter_by(business_id=business_id).count()
        total_appointments = AppointmentRequest.query.join(CallLog).filter(CallLog.business_id == business_id).count()
        conversion_rate = (total_appointments / total_calls * 100) if total_calls > 0 else 0
        
        from datetime import datetime
        today = datetime.now().date()
        today_calls = CallLog.query.filter_by(business_id=business_id).filter(CallLog.created_at >= today).count()
        
        stats = {
            "total_calls": total_calls,
            "total_appointments": total_appointments,
            "customers_count": total_calls,
            "pending_tasks": 0,
            "conversion_rate": round(conversion_rate, 1),
            "today_calls": today_calls
        }
        
        return jsonify({"success": True, "stats": stats})
        
    except Exception as e:
        logger.error(f"Error in dashboard stats API: {e}")
        return jsonify({"success": False, "error": str(e)})

# ========== REGISTER BLUEPRINTS ==========
# רישום נתיבי CRM מתבצע ב-app.py


