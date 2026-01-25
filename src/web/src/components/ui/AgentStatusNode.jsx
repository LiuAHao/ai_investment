import React from 'react';
import { Loader2 } from 'lucide-react';

const AgentStatusNode = ({ icon: Icon, label, status }) => (
  <div className={`flex flex-col items-center gap-2 transition-all duration-500 ${status === 'active' ? 'opacity-100 scale-110' : status === 'done' ? 'opacity-50' : 'opacity-30'}`}>
    <div className={`w-12 h-12 rounded-full flex items-center justify-center border-2 
      ${status === 'active' ? 'border-red-500 bg-red-500/20 text-red-400' : 
        status === 'done' ? 'border-blue-500 bg-blue-500/10 text-blue-400' : 
        'border-slate-700 bg-slate-800 text-slate-600'}`}>
      {status === 'active' ? <Loader2 className="animate-spin w-6 h-6" /> : <Icon className="w-6 h-6" />}
    </div>
    <span className="text-xs font-medium text-slate-400">{label}</span>
  </div>
);

export default AgentStatusNode;
