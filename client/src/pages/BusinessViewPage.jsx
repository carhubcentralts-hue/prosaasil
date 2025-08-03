import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { User, Loader, CheckCircle } from 'lucide-react';

const BusinessViewPage = () => {
  const { id } = useParams();
  const [taking, setTaking] = useState(true);
  const [error, setError] = useState(null);
  const [business, setBusiness] = useState(null);
  const [message, setMessage] = useState('מתחיל השתלטות...');
  const [success, setSuccess] = useState(false);

  console.log('🔥 BusinessViewPage: השתלטות אוטומטית על עסק ID:', id);

  useEffect(() => {
    if (id) {
      performAutomaticTakeover();
    }
  }, [id]);

  const performAutomaticTakeover = async () => {
    try {
      setMessage('טוען נתוני עסק...');
      console.log('🔥 מתחיל השתלטות אוטומטית על עסק:', id);
      
      // קבלת נתוני העסק
      const businessResponse = await axios.get(`/api/admin/businesses/${id}`);
      setBusiness(businessResponse.data);
      setMessage(`מבצע השתלטות על עסק: ${businessResponse.data.name}`);
      
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // השתלטות על העסק
      const response = await axios.post(`/api/admin/impersonate/${id}`);
      
      if (response.data.token) {
        console.log('✅ השתלטות הצליחה על עסק:', response.data.business_name);
        setMessage('השתלטות הצליחה! מעביר למערכת העסק...');
        setSuccess(true);
        
        // שמירת הטוקן המקורי
        const currentToken = localStorage.getItem('token');
        localStorage.setItem('originalAdminToken', currentToken);
        
        // שמירת הטוקן החדש
        localStorage.setItem('token', response.data.token);
        localStorage.setItem('viewingAsBusinessId', id);
        localStorage.setItem('isImpersonating', 'true');
        localStorage.setItem('business_id', id);
        localStorage.setItem('business_name', response.data.business_name);
        localStorage.setItem('user_name', 'מנהל (במצב השתלטות)');
        
        console.log('🚀 מעביר למערכת העסק עם שליטה מלאה');
        
        // מעבר למערכת העסק
        setTimeout(() => {
          window.location.href = '/business/dashboard';
        }, 1500);
      }
    } catch (error) {
      console.error('Error during automatic takeover:', error);
      setError('שגיאה בהשתלטות על מערכת העסק');
      setMessage('שגיאה בהשתלטות');
      setTaking(false);
    }
  };

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center font-hebrew max-w-md bg-white rounded-lg shadow-lg p-8">
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            <h2 className="text-xl font-bold mb-2">שגיאה בהשתלטות</h2>
            <p>{error}</p>
          </div>
          <button 
            onClick={() => window.location.href = '/'}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 font-hebrew"
          >
            חזור לדשבורד מנהל
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center" dir="rtl">
      <div className="bg-white rounded-3xl shadow-2xl p-12 max-w-2xl w-full mx-4">
        <div className="text-center font-hebrew">
          
          {/* אייקון מרכזי */}
          <div className="mb-8">
            <div className="w-24 h-24 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg">
              {success ? (
                <CheckCircle className="w-12 h-12 text-white" />
              ) : (
                <User className="w-12 h-12 text-white" />
              )}
            </div>
            <h1 className="text-3xl font-bold text-gray-900 mb-3">
              השתלטות על מערכת העסק
            </h1>
            <p className="text-gray-600 text-lg">
              מבצע השתלטות אוטומטית על עסק #{id}
            </p>
          </div>

          {/* נתוני עסק */}
          {business && (
            <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl p-6 mb-8 border border-blue-200">
              <h3 className="font-bold text-2xl text-gray-900 mb-3">{business.name}</h3>
              <div className="grid grid-cols-2 gap-4 text-right">
                <div>
                  <p className="text-gray-600 font-medium">סוג עסק:</p>
                  <p className="text-gray-900 font-bold">{business.type}</p>
                </div>
                <div>
                  <p className="text-gray-600 font-medium">טלפון:</p>
                  <p className="text-gray-900 font-bold">{business.phone}</p>
                </div>
              </div>
            </div>
          )}

          {/* סטטוס השתלטות */}
          <div className="mb-8">
            <div className="flex items-center justify-center gap-4 mb-6">
              {!success && <Loader className="w-8 h-8 text-blue-600 animate-spin" />}
              <span className="text-xl font-bold text-gray-900">{message}</span>
            </div>
            
            {/* פס התקדמות מעוצב */}
            <div className="w-full bg-gray-200 rounded-full h-4 shadow-inner">
              <div 
                className={`h-4 rounded-full transition-all duration-2000 ${success ? 'bg-green-500' : 'bg-gradient-to-r from-blue-500 to-purple-500'}`}
                style={{ width: success ? '100%' : (taking ? '75%' : '25%') }}
              ></div>
            </div>
          </div>

          {/* הודעת סטטוס */}
          <div className="text-gray-600 mb-8">
            {success ? (
              <div className="text-green-600 font-bold text-lg">
                <p>✅ השתלטות הושלמה בהצלחה!</p>
                <p>מעביר אותך למערכת העסק...</p>
              </div>
            ) : (
              <div>
                <p className="text-lg">השתלטות בתהליך...</p>
                <p>תועבר אוטומטית למערכת העסק עם שליטה מלאה</p>
              </div>
            )}
          </div>

          {/* כפתור חזרה */}
          <div className="border-t pt-6">
            <button 
              onClick={() => window.location.href = '/'}
              className="text-gray-500 hover:text-gray-700 underline font-hebrew text-sm"
            >
              ביטול וחזרה לדשבורד מנהל
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BusinessViewPage;