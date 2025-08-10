import React from 'react';

const LoadingSpinner = ({ message = "טוען..." }) => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-purple-50">
      <div className="text-center">
        <div className="loading-spinner mx-auto mb-4"></div>
        <p className="text-gray-600 font-assistant text-lg">{message}</p>
      </div>
    </div>
  );
};

export default LoadingSpinner;