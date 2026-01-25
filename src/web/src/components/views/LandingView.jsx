import React from 'react';
import { TrendingUp, ArrowRight } from 'lucide-react';

const LandingView = ({ setViewState }) => {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Navbar */}
      <nav className="w-full py-6 px-4 md:px-8 flex justify-between items-center z-50">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-red-500 to-orange-600 flex items-center justify-center shadow-lg shadow-red-500/20">
            <TrendingUp className="text-white w-6 h-6" />
          </div>
          <span className="font-bold text-xl tracking-tight text-white">AI投资助手</span>
        </div>
        <div className="flex gap-4">
          <button 
            onClick={() => setViewState('login')}
            className="text-slate-300 hover:text-white font-medium px-4 py-2 transition-colors"
          >
            登录
          </button>
          <button 
            onClick={() => setViewState('register')}
            className="bg-white text-slate-900 hover:bg-slate-100 font-bold px-5 py-2 rounded-full transition-all shadow-lg hover:shadow-white/10"
          >
            免费注册
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="flex-1 flex flex-col justify-center items-center px-4 text-center relative z-10 pt-12 pb-20">
        
        <h1 className="text-5xl md:text-7xl font-bold text-white mb-6 tracking-tight max-w-4xl leading-tight animate-in fade-in slide-in-from-bottom-6 duration-700 delay-100">
          用 <span className="text-transparent bg-clip-text bg-gradient-to-r from-red-400 to-orange-500">AI 智能</span> 重塑 <br/>
          你的投资决策体系
        </h1>
        
        <p className="text-lg md:text-xl text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed animate-in fade-in slide-in-from-bottom-8 duration-700 delay-200">
          整合全网舆情、机构研报与资金流向。为您提供机构级的深度投研报告，
          让每一次交易都更有把握。
        </p>

        <div className="flex flex-col md:flex-row gap-4 animate-in fade-in slide-in-from-bottom-10 duration-700 delay-300">
          <button 
            onClick={() => setViewState('register')}
            className="px-8 py-4 bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-500 hover:to-orange-500 text-white rounded-xl font-bold text-lg transition-all shadow-xl shadow-red-500/25 flex items-center justify-center gap-2 group"
          >
            立即开始使用
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>
      </div>

      {/* Footer */}
      <footer className="w-full py-8 text-center text-slate-600 text-sm relative z-10 border-t border-white/5">
        <p>© 2024 AI Investment Agent. All rights reserved.</p>
      </footer>
    </div>
  );
};

export default LandingView;
