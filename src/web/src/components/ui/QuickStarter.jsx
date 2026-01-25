import React from 'react';
import { Activity } from 'lucide-react';

const QuickStarter = ({ text, onClick }) => (
  <button 
    onClick={onClick}
    className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm text-slate-300 transition-colors flex items-center gap-2"
  >
    <Activity className="w-3 h-3 text-red-400" />
    {text}
  </button>
);

export default QuickStarter;
