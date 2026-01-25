import React, { useState } from 'react';
import { TrendingUp, Mail, Lock, User, ArrowRight, Loader2, ArrowLeft } from 'lucide-react';

const AuthView = ({ viewState, setViewState }) => {
  const [isLoading, setIsLoading] = useState(false);

  const isLogin = viewState === 'login';
  const isRegister = viewState === 'register';

  const handleSubmit = (e) => {
    e.preventDefault();
    setIsLoading(true);
    // Simulate network request
    setTimeout(() => {
      setIsLoading(false);
      setViewState('main');
    }, 1500);
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 relative z-10">
      <div className="w-full max-w-md bg-slate-900/60 backdrop-blur-xl border border-white/10 p-8 rounded-3xl shadow-2xl animate-in fade-in zoom-in-95 duration-500 relative">
        
        {/* Back Button */}
        <button 
          onClick={() => setViewState('landing')}
          className="absolute left-6 top-6 p-2 text-slate-400 hover:text-white transition-colors rounded-full hover:bg-white/5"
          aria-label="返回首页"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="text-center mb-8 mt-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-red-500 to-orange-600 flex items-center justify-center shadow-lg shadow-red-500/20 mx-auto mb-4">
            <TrendingUp className="text-white w-7 h-7" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">
            {isLogin ? '欢迎回来' : '创建新账户'}
          </h2>
          <p className="text-slate-400 text-sm">
            {isLogin ? '登录以继续您的投资之旅' : '加入数万名智能投资者的行列'}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {isRegister && (
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-300 ml-1">姓名</label>
              <div className="relative">
                <input 
                  type="text" 
                  placeholder="请输入您的姓名"
                  className="w-full bg-slate-800/50 border border-slate-700 text-white rounded-xl px-4 py-3 pl-10 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors"
                  required
                />
                <User className="w-4 h-4 text-slate-500 absolute left-3 top-3.5" />
              </div>
            </div>
          )}

          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-300 ml-1">电子邮箱</label>
            <div className="relative">
              <input 
                type="email" 
                placeholder="name@example.com"
                className="w-full bg-slate-800/50 border border-slate-700 text-white rounded-xl px-4 py-3 pl-10 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors"
                required
              />
              <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-3.5" />
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between items-center ml-1">
                <label className="text-xs font-medium text-slate-300">密码</label>
            </div>
            <div className="relative">
              <input 
                type="password" 
                placeholder="••••••••"
                className="w-full bg-slate-800/50 border border-slate-700 text-white rounded-xl px-4 py-3 pl-10 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500 transition-colors"
                required
              />
              <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-3.5" />
            </div>
          </div>

          <button 
            type="submit" 
            disabled={isLoading}
            className="w-full bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-500 hover:to-orange-500 text-white font-bold py-3.5 rounded-xl shadow-lg shadow-red-500/25 transition-all mt-6 flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                正在处理...
              </>
            ) : (
              <>
                {isLogin ? '登录' : '立即注册'}
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-8 text-center">
          <p className="text-sm text-slate-400">
            {isLogin ? '还没有账号?' : '已有账号?'}
            <button 
              onClick={() => setViewState(isLogin ? 'register' : 'login')}
              className="ml-2 text-white font-medium hover:text-red-400 transition-colors underline decoration-slate-600 underline-offset-4"
            >
              {isLogin ? '免费注册' : '立即登录'}
            </button>
          </p>
        </div>

      </div>
    </div>
  );
};

export default AuthView;
