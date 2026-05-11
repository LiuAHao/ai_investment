import React from 'react';

const FormFeedback = ({ 
  type = 'error', 
  message, 
  visible = true,
  className = '' 
}) => {
  if (!visible || !message) return null;

  const typeConfig = {
    error: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      text: 'text-red-700',
      icon: '✗',
    },
    success: {
      bg: 'bg-green-50',
      border: 'border-green-200',
      text: 'text-green-700',
      icon: '✓',
    },
    warning: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-200',
      text: 'text-yellow-700',
      icon: '⚠',
    },
    info: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      text: 'text-blue-700',
      icon: 'ℹ',
    },
  };

  const config = typeConfig[type] || typeConfig.error;

  return (
    <div className={`${config.bg} ${config.border} border rounded-md p-3 ${className}`}>
      <div className="flex items-center gap-2">
        <span className={`${config.text} font-bold`}>{config.icon}</span>
        <span className={`${config.text} text-sm`}>{message}</span>
      </div>
    </div>
  );
};

export default FormFeedback;
