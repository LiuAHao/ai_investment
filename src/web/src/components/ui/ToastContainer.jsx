import React from 'react';
import Toast from './Toast';
import { useFeedback } from '../../contexts/FeedbackContext';

const ToastContainer = () => {
  const { toasts, removeToast } = useFeedback();

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2">
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          duration={toast.duration}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </div>
  );
};

export default ToastContainer;
