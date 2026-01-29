import React from 'react';
import { ArrowRight, Mail, Phone, Lock } from 'lucide-react';

const ProfileView = ({ setViewState, user }) => (
  <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-right-4 duration-500">
    <div className="flex items-center gap-4 mb-8">
      <button 
        onClick={() => setViewState('main')}
        className="text-slate-400 hover:text-white transition-colors"
      >
        <ArrowRight className="w-5 h-5 rotate-180" />
      </button>
      <h1 className="text-3xl font-bold text-white">个人账户</h1>
    </div>

    <div className="grid gap-6">
      {/* Profile Card */}
      <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 p-6 shadow-xl">
        <div className="flex items-start gap-6">
          <div className="w-24 h-24 rounded-full bg-gradient-to-br from-red-500 to-orange-600 flex items-center justify-center text-white text-3xl font-bold shadow-lg shadow-red-500/20">
            {(user?.nickname || user?.username || 'AI')[0]}
          </div>
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-white mb-2">{user?.nickname || user?.username || '用户'}</h2>
            <p className="text-slate-400 mb-4">标准账号</p>
            <div className="flex gap-3">
              <button className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium transition-colors shadow-lg shadow-red-500/20">
                编辑资料
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Account Info */}
      <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 p-6 shadow-xl">
        <h3 className="text-lg font-bold text-white mb-4">账户信息</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between py-3 border-b border-white/10">
            <div className="flex items-center gap-3">
              <Mail className="w-5 h-5 text-slate-500" />
              <div>
                <p className="text-sm font-medium text-slate-300">电子邮箱</p>
                <p className="text-xs text-slate-500">{user?.email || '未设置邮箱'}</p>
              </div>
            </div>
            <button className="text-red-400 text-sm hover:text-red-300">修改</button>
          </div>
          <div className="flex items-center justify-between py-3 border-b border-white/10">
            <div className="flex items-center gap-3">
              <Phone className="w-5 h-5 text-slate-500" />
              <div>
                <p className="text-sm font-medium text-slate-300">手机号码</p>
                <p className="text-xs text-slate-500">+86 138****8888</p>
              </div>
            </div>
            <button className="text-red-400 text-sm hover:text-red-300">修改</button>
          </div>
          <div className="flex items-center justify-between py-3">
            <div className="flex items-center gap-3">
              <Lock className="w-5 h-5 text-slate-500" />
              <div>
                <p className="text-sm font-medium text-slate-300">登录密码</p>
                <p className="text-xs text-slate-500">上次修改于 2024-12-15</p>
              </div>
            </div>
            <button className="text-red-400 text-sm hover:text-red-300">修改</button>
          </div>
        </div>
      </div>
    </div>
  </div>
);

export default ProfileView;
