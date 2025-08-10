import axios from 'axios';

const API_BASE = '/api';

// יצירת instance עם הגדרות ברירת מחדל
const apiClient = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000
});

// Interceptor לטיפול בשגיאות
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // מחיקת מצב האימות במקרה של 401
      localStorage.removeItem('authToken');
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  // התחברות
  async login(email, password) {
    try {
      const response = await apiClient.post('/auth/login', { email, password });
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.message || 'שגיאה בהתחברות');
    }
  },

  // יציאה
  async logout() {
    try {
      await apiClient.post('/auth/logout');
      return { success: true };
    } catch (error) {
      throw new Error(error.response?.data?.message || 'שגיאה ביציאה');
    }
  },

  // קבלת פרטי משתמש נוכחי
  async getMe() {
    try {
      const response = await apiClient.get('/auth/me');
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.message || 'שגיאה בקבלת פרטי משתמש');
    }
  },

  // בדיקת מצב חיבור
  async checkHealth() {
    try {
      const response = await apiClient.get('/health');
      return response.data;
    } catch (error) {
      throw new Error('השרת לא זמין');
    }
  }
};

export default apiClient;