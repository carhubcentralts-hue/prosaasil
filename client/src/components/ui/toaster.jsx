import React from 'react';

export const Toaster = () => {
  // Simple toast component placeholder
  return (
    <div id="toast-container" className="fixed top-4 right-4 z-50">
      {/* Toast notifications will appear here */}
    </div>
  );
};

export const useToast = () => {
  const toast = ({ title, description, variant = 'default' }) => {
    console.log('Toast:', { title, description, variant });
    
    // Simple alert for now - can be enhanced later
    if (variant === 'destructive') {
      alert(`שגיאה: ${title}\n${description}`);
    } else {
      alert(`${title}\n${description}`);
    }
  };

  return { toast };
};