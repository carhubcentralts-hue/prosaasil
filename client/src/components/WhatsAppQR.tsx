import { useState, useEffect } from 'react';

interface WhatsAppStatus {
  ok: boolean;
  connected: boolean;
  status: string;
  qr_available: boolean;
  last_connected?: string;
}

interface WhatsAppQRProps {
  className?: string;
}

export default function WhatsAppQR({ className = "" }: WhatsAppQRProps) {
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);
  const [qrCode, setQrCode] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");

  const checkStatus = async () => {
    try {
      const response = await fetch('/api/whatsapp/status');
      const data = await response.json();
      setStatus(data);
      
      // If not connected and QR available, get QR code
      if (!data.connected && data.qr_available) {
        const qrResponse = await fetch('/api/whatsapp/qr');
        const qrData = await qrResponse.json();
        if (qrData.ok && qrData.qr_code) {
          setQrCode(qrData.qr_code);
        }
      }
      
      setLoading(false);
      setError("");
    } catch (err) {
      setError("Failed to check WhatsApp status");
      setLoading(false);
    }
  };

  useEffect(() => {
    checkStatus();
    // Check status every 5 seconds
    const interval = setInterval(checkStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const generateQRCodeURL = (data: string) => {
    return `https://api.qrserver.com/v1/create-qr-code/?size=256x256&data=${encodeURIComponent(data)}`;
  };

  if (loading) {
    return (
      <div className={`bg-white rounded-lg border border-gray-200 p-6 ${className}`}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-6 h-6 bg-green-600 rounded-full flex items-center justify-center">
            <span className="text-white text-xs">📱</span>
          </div>
          <h3 className="text-lg font-semibold text-gray-900">WhatsApp Connection</h3>
        </div>
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="text-gray-500 mt-2">Checking WhatsApp status...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`bg-white rounded-lg border border-red-200 p-6 ${className}`}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-6 h-6 bg-red-600 rounded-full flex items-center justify-center">
            <span className="text-white text-xs">✗</span>
          </div>
          <h3 className="text-lg font-semibold text-gray-900">WhatsApp Connection</h3>
        </div>
        <div className="text-center py-8">
          <p className="text-red-600 mb-4">{error}</p>
          <button 
            onClick={checkStatus}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            🔄
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white rounded-lg border border-gray-200 p-6 ${className}`}>
      <div className="flex items-center gap-3 mb-4">
        {status?.connected ? (
          <div className="w-6 h-6 bg-green-600 rounded-full flex items-center justify-center">
            <span className="text-white text-xs">✓</span>
          </div>
        ) : (
          <div className="w-6 h-6 bg-orange-600 rounded-full flex items-center justify-center">
            <span className="text-white text-xs">×</span>
          </div>
        )}
        <h3 className="text-lg font-semibold text-gray-900">WhatsApp Connection</h3>
        <div className={`px-2 py-1 rounded-full text-xs font-medium ${
          status?.connected 
            ? 'bg-green-100 text-green-800' 
            : 'bg-orange-100 text-orange-800'
        }`}>
          {status?.connected ? 'Connected' : 'Disconnected'}
        </div>
      </div>

      {status?.connected ? (
        <div className="text-center py-8">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">📱</span>
          </div>
          <h4 className="text-lg font-semibold text-gray-900 mb-2">WhatsApp Connected!</h4>
          <p className="text-gray-600 mb-2">Your WhatsApp is ready to send and receive messages.</p>
          {status?.last_connected && (
            <p className="text-sm text-gray-500">
              Connected: {new Date(status.last_connected).toLocaleString()}
            </p>
          )}
        </div>
      ) : qrCode ? (
        <div className="text-center">
          <h4 className="text-lg font-semibold text-gray-900 mb-4">Scan QR Code</h4>
          <div className="flex justify-center mb-4">
            <img 
              src={generateQRCodeURL(qrCode)} 
              alt="WhatsApp QR Code"
              className="w-64 h-64 border border-gray-200 rounded-lg"
              data-testid="whatsapp-qr-code"
            />
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h5 className="font-semibold text-blue-900 mb-2">Instructions:</h5>
            <ol className="text-sm text-blue-800 space-y-1 text-right" dir="rtl">
              <li>1. פתח את WhatsApp במכשיר הטלפון שלך</li>
              <li>2. לך ל"הגדרות" ← "מכשירים מקושרים"</li>
              <li>3. לחץ על "קשר מכשיר"</li>
              <li>4. סרוק את הקוד QR הזה</li>
            </ol>
          </div>
          <button 
            onClick={checkStatus}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            data-testid="refresh-whatsapp-status"
          >
            🔄
            Refresh Status
          </button>
        </div>
      ) : (
        <div className="text-center py-8">
          <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">📱</span>
          </div>
          <h4 className="text-lg font-semibold text-gray-900 mb-2">WhatsApp Disconnected</h4>
          <p className="text-gray-600 mb-4">Waiting for QR code generation...</p>
          <button 
            onClick={checkStatus}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            data-testid="refresh-whatsapp-status"
          >
            🔄
            Refresh Status
          </button>
        </div>
      )}
    </div>
  );
}