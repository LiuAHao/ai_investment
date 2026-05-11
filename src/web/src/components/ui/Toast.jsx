import React, { useEffect, useState } from 'react';

const Toast = ({ message, type = 'info', duration = 3000, onClose }) => {
  const [visible, setVisible] = useState(true);
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    const startTime = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, 100 - (elapsed / duration) * 100);
      setProgress(remaining);
      
      if (remaining <= 0) {
        clearInterval(interval);
        setVisible(false);
        onClose?.();
      }
    }, 50);

    return () => clearInterval(interval);
  }, [duration, onClose]);

  if (!visible) return null;

  const typeConfig = {
    success: {
      bg: 'bg-green-500',
      icon: '✓',
      progressBg: 'bg-green-300',
    },
    error: {
      bg: 'bg-red-500',
      icon: '✗',
      progressBg: 'bg-red-300',
    },
    warning: {
      bg: 'bg-yellow-500',
      icon: '⚠',
      progressBg: 'bg-yellow-300',
    },
    info: {
      bg: 'bg-blue-500',
      icon: 'ℹ',
      progressBg: 'bg-blue-300',
    },
  };

  const config = typeConfig[type] || typeConfig.info;

  return (
    <div className={`fixed top-4 right-4 z-50 ${config.bg} text-white rounded-lg shadow-lg overflow-hidden min-w-[300px]`}>
      <div className="p-4 flex items-center gap-3">
        <span className="text-lg font-bold">{config.icon}</span>
        <span className="flex-1">{message}</span>
        <button
          onClick={() => {
            setVisible(false);
            onClose?.();
          }}
          className="text-white hover:text-gray-200 transition-colors"
        >
          ✕
        </button>
      </div>
      <div className="h-1 bg-black bg-opacity-20">
        <div
          className={`h-full ${config.progressBg} transition-all duration-100 ease-linear`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
};

export default Toast;
