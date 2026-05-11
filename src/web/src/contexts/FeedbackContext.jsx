/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useCallback } from 'react';

const FeedbackContext = createContext();

export const useFeedback = () => {
  const context = useContext(FeedbackContext);
  if (!context) {
    throw new Error('useFeedback must be used within a FeedbackProvider');
  }
  return context;
};

export const FeedbackProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);
  const [loadingStates, setLoadingStates] = useState({});

  const addToast = useCallback((message, type = 'info', duration = 3000) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type, duration }]);
    
    setTimeout(() => {
      setToasts(prev => prev.filter(toast => toast.id !== id));
    }, duration);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);

  const setLoading = useCallback((key, isLoading) => {
    setLoadingStates(prev => ({ ...prev, [key]: isLoading }));
  }, []);

  const isLoading = useCallback((key) => {
    return loadingStates[key] || false;
  }, [loadingStates]);

  const showSuccess = useCallback((message) => {
    addToast(message, 'success');
  }, [addToast]);

  const showError = useCallback((message) => {
    addToast(message, 'error');
  }, [addToast]);

  const showWarning = useCallback((message) => {
    addToast(message, 'warning');
  }, [addToast]);

  const showInfo = useCallback((message) => {
    addToast(message, 'info');
  }, [addToast]);

  return (
    <FeedbackContext.Provider value={{
      toasts,
      addToast,
      removeToast,
      setLoading,
      isLoading,
      showSuccess,
      showError,
      showWarning,
      showInfo,
    }}>
      {children}
    </FeedbackContext.Provider>
  );
};

export default FeedbackContext;