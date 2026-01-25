import React from 'react';
import { ArrowRight, Shield } from 'lucide-react';

const SettingsView = ({ setViewState }) => (
  <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-right-4 duration-500">
    <div className="flex items-center gap-4 mb-8">
      <button 
        onClick={() => setViewState('main')}
        className="text-slate-400 hover:text-white transition-colors"
      >
        <ArrowRight className="w-5 h-5 rotate-180" />
      </button>
      <h1 className="text-3xl font-bold text-white">设置</h1>
    </div>

    <div className="grid gap-6">
      {/* Privacy Settings */}
      <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 p-6 shadow-xl">
        <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-blue-400" />
          隐私与安全
        </h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm font-medium text-slate-300">数据分享</p>
              <p className="text-xs text-slate-500">用于改进 AI 模型</p>
            </div>
            <div className="w-12 h-6 bg-red-500 rounded-full relative cursor-pointer shadow-inner">
              <div className="absolute right-1 top-1 w-4 h-4 bg-white rounded-full shadow-sm"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

export default SettingsView;
