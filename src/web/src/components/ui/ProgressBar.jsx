import React from 'react';

const ProgressBar = ({ progress }) => (
  <div className="w-full bg-slate-800 h-1 rounded-full mt-8 overflow-hidden">
    <div 
      className="bg-gradient-to-r from-red-500 to-orange-500 h-full transition-all duration-300 ease-out"
      style={{ width: `${progress}%` }}
    />
  </div>
);

export default ProgressBar;
