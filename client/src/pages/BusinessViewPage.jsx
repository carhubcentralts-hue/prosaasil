import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { User, ArrowRight, Loader } from 'lucide-react';

const BusinessTakeoverPage = () => {
  const { id } = useParams();
  const [loading, setLoading] = useState(true);
  const [taking, setTaking] = useState(false);
  const [error, setError] = useState(null);
  const [business, setBusiness] = useState(null);
  const [message, setMessage] = useState('מתחיל השתלטות...');

  console.log('🔥 BusinessTakeoverPage: מתחיל השתלטות על עסק ID:', id);

  useEffect(() => {
    if (id) {
      performTakeover();
    }
  }, [id]);

  const performTakeover = async () => {
    try {
      setTaking(true);
      setMessage('טוען נתוני עסק...');
      console.log('🔥 מתחיל השתלטות אוטומטית על עסק:', id);
      
      // קודם נקבל את נתוני העסק
      const businessResponse = await axios.get(`/api/admin/businesses/${id}`);
      setBusiness(businessResponse.data);
      setMessage(`מבצע השתלטות על עסק: ${businessResponse.data.name}`);
      
      // עכשיו נבצע השתלטות
      const response = await axios.post(`/api/admin/impersonate/${id}`);
      
      if (response.data.token) {
        console.log('✅ השתלטות הצליחה על עסק:', response.data.business_name);
        setMessage('השתלטות הצליחה! מעביר למערכת העסק...');
        
        // שמירת הטוקן המקורי
        const currentToken = localStorage.getItem('token');
        localStorage.setItem('originalAdminToken', currentToken);
        
        // שמירת הטוקן החדש למערכת העסק
        localStorage.setItem('token', response.data.token);
        localStorage.setItem('viewingAsBusinessId', id);
        localStorage.setItem('isImpersonating', 'true');
        localStorage.setItem('business_id', id);
        localStorage.setItem('business_name', response.data.business_name);
        localStorage.setItem('user_name', 'מנהל (במצב השתלטות)');
        
        console.log('🚀 מעביר למערכת העסק עם שליטה מלאה');
        
        // המתנה קצרה ומעבר למערכת העסק
        setTimeout(() => {
          window.location.href = '/business-dashboard';
        }, 1500);
      }
    } catch (error) {
      console.error('Error during takeover:', error);
      setError('שגיאה בהשתלטות על מערכת העסק');
      setMessage('שגיאה בהשתלטות');
      setLoading(false);
      setTaking(false);
    }
  };

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center font-hebrew max-w-md">
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
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-blue-100 flex items-center justify-center" dir="rtl">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-lg w-full mx-4">
        <div className="text-center font-hebrew">
          {/* כותרת */}
          <div className="mb-6">
            <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
              <User className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              השתלטות על מערכת העסק
            </h1>
            <p className="text-gray-600">
              מבצע השתלטות על עסק #{id}
            </p>
          </div>

          {/* נתוני עסק */}
          {business && (
            <div className="bg-gray-50 rounded-lg p-4 mb-6">
              <h3 className="font-bold text-lg text-gray-900 mb-2">{business.name}</h3>
              <p className="text-gray-600">סוג: {business.type}</p>
              <p className="text-gray-600">טלפון: {business.phone}</p>
            </div>
          )}

          {/* סטטוס השתלטות */}
          <div className="mb-6">
            <div className="flex items-center justify-center gap-3 mb-4">
              <Loader className="w-6 h-6 text-blue-600 animate-spin" />
              <span className="text-lg font-medium text-gray-900">{message}</span>
            </div>
            
            {/* פס התקדמות */}
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-1000"
                style={{ width: taking ? '80%' : '20%' }}
              ></div>
            </div>
          </div>

          {/* הודעת המתנה */}
          <div className="text-sm text-gray-500">
            <p>זה יקח רק רגע...</p>
            <p>תועבר אוטומטית למערכת העסק עם שליטה מלאה</p>
          </div>

          {/* כפתור חזרה במקרה של בעיה */}
          <div className="mt-8">
            <button 
              onClick={() => window.location.href = '/'}
              className="text-gray-600 hover:text-gray-800 underline font-hebrew"
            >
              חזור לדשבורד מנהל
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BusinessTakeoverPage;