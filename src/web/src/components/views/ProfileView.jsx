import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, Mail, Phone, Lock, User, Crown, Zap, Shield, Star } from 'lucide-react';
import { updatePassword, updatePhone, updateProfile, fetchQuota, fetchTiers, upgradeTier } from '../../services/apiClient';

const ProfileView = ({ setViewState, user, onProfileUpdated }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editMode, setEditMode] = useState('nickname');
  const [nickname, setNickname] = useState(user?.nickname || '');
  const [email, setEmail] = useState(user?.email || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [quotaData, setQuotaData] = useState(null);
  const [tiersData, setTiersData] = useState([]);
  const [isUpgrading, setIsUpgrading] = useState(false);
  const [upgradeMsg, setUpgradeMsg] = useState('');
  const nicknameRef = useRef(null);
  const emailRef = useRef(null);
  const phoneRef = useRef(null);
  const currentPasswordRef = useRef(null);

  const createdAtText = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('zh-CN')
    : '—';

  useEffect(() => {
    setNickname(user?.nickname || '');
    setEmail(user?.email || '');
    setPhone(user?.phone || '');
  }, [user]);

  // 加载配额和等级信息
  useEffect(() => {
    const loadTierData = async () => {
      try {
        const [q, t] = await Promise.all([fetchQuota(), fetchTiers()]);
        setQuotaData(q);
        setTiersData(t?.tiers || []);
      } catch (err) {
        // 静默失败，不影响主要功能
      }
    };
    loadTierData();
  }, [user?.user_tier]);

  useEffect(() => {
    if (!isEditing) return;
    if (editMode === 'email' && emailRef.current) {
      emailRef.current.focus();
      return;
    }
    if (editMode === 'phone' && phoneRef.current) {
      phoneRef.current.focus();
      return;
    }
    if (editMode === 'password' && currentPasswordRef.current) {
      currentPasswordRef.current.focus();
      return;
    }
    if (nicknameRef.current) {
      nicknameRef.current.focus();
    }
  }, [isEditing, editMode]);

  const openEditor = (mode = 'nickname') => {
    setEditMode(mode);
    setError('');
    setIsEditing(true);
  };

  const closeEditor = () => {
    setIsEditing(false);
    setError('');
  };

  // 等级相关配置
  const tierConfig = {
    free: { label: '免费版', color: 'from-slate-500 to-slate-600', textColor: 'text-slate-300', icon: User, borderColor: 'border-slate-500/30' },
    pro: { label: '专业版', color: 'from-blue-500 to-cyan-500', textColor: 'text-blue-300', icon: Zap, borderColor: 'border-blue-500/30' },
    premium: { label: '旗舰版', color: 'from-amber-500 to-yellow-500', textColor: 'text-amber-300', icon: Crown, borderColor: 'border-amber-500/30' },
  };
  const currentTier = user?.user_tier || 'free';
  const currentTierConfig = tierConfig[currentTier] || tierConfig.free;
  const TierIcon = currentTierConfig.icon;

  const handleUpgrade = async (tier) => {
    if (tier === currentTier) return;
    setIsUpgrading(true);
    setUpgradeMsg('');
    try {
      const result = await upgradeTier(tier);
      setUpgradeMsg(result?.message || '升级成功');
      // 刷新用户信息
      if (onProfileUpdated) {
        onProfileUpdated({ ...user, user_tier: tier });
      }
      // 刷新配额
      const q = await fetchQuota();
      setQuotaData(q);
    } catch (err) {
      setUpgradeMsg(err?.message || '升级失败');
    } finally {
      setIsUpgrading(false);
    }
  };

  // 配额使用率渲染
  const renderQuotaBar = (label, used, limit) => {
    const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
    const isHigh = pct >= 80;
    return (
      <div className="space-y-1.5">
        <div className="flex justify-between text-xs">
          <span className="text-slate-400">{label}</span>
          <span className={isHigh ? 'text-red-400 font-medium' : 'text-slate-400'}>{used} / {limit}</span>
        </div>
        <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${isHigh ? 'bg-gradient-to-r from-red-500 to-orange-500' : 'bg-gradient-to-r from-blue-500 to-cyan-400'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    );
  };

  const handleSave = async () => {
    if (editMode === 'notice') {
      closeEditor();
      return;
    }
    setIsSaving(true);
    setError('');
    try {
      if (editMode === 'password') {
        if (!currentPassword || !newPassword) {
          setError('请输入原密码与新密码');
          return;
        }
        if (newPassword.length < 6) {
          setError('新密码长度不能少于 6 位');
          return;
        }
        if (newPassword !== confirmPassword) {
          setError('两次输入的新密码不一致');
          return;
        }
        await updatePassword(currentPassword, newPassword);
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
        closeEditor();
        return;
      }

      if (editMode === 'phone') {
        const payloadPhone = phone.trim() || null;
        const result = await updatePhone(payloadPhone);
        const updatedUser = result?.user || { ...user, phone: payloadPhone };
        if (onProfileUpdated) {
          onProfileUpdated(updatedUser);
        }
        closeEditor();
        return;
      }

      const payloadNickname = editMode === 'nickname' ? (nickname.trim() || null) : undefined;
      const payloadEmail = editMode === 'email' ? (email.trim() || null) : undefined;
      const result = await updateProfile(payloadNickname, payloadEmail);
      const updatedUser = result?.user || {
        ...user,
        ...(payloadNickname !== undefined ? { nickname: payloadNickname } : {}),
        ...(payloadEmail !== undefined ? { email: payloadEmail } : {}),
      };
      if (onProfileUpdated) {
        onProfileUpdated(updatedUser);
      }
      closeEditor();
    } catch (err) {
      setError(err?.message || '更新失败，请稍后重试');
    } finally {
      setIsSaving(false);
    }
  };

  return (
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
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-red-500 to-orange-600 flex items-center justify-center text-white text-base font-bold shadow-lg shadow-red-500/20 text-center px-2 leading-tight">
              {user?.nickname || user?.username || 'AI'}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <h2 className="text-2xl font-bold text-white">{user?.nickname || user?.username || '用户'}</h2>
                <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gradient-to-r ${currentTierConfig.color} text-white shadow-lg`}>
                  <TierIcon className="w-3 h-3" />
                  {currentTierConfig.label}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-2 gap-x-6 text-xs text-slate-400">
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">用户名</span>
                  <span className="text-slate-200">{user?.username || '—'}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">邮箱</span>
                  <span className="text-slate-200">{user?.email || '—'}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">手机号</span>
                  <span className="text-slate-200">{user?.phone || '—'}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">创建时间</span>
                  <span className="text-slate-200">{createdAtText}</span>
                </div>
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
                <User className="w-5 h-5 text-slate-500" />
                <div>
                  <p className="text-sm font-medium text-slate-300">昵称</p>
                  <p className="text-xs text-slate-500">{user?.nickname || user?.username || '未设置昵称'}</p>
                </div>
              </div>
              <button
                onClick={() => openEditor('nickname')}
                className="text-red-400 text-sm hover:text-red-300"
              >
                修改
              </button>
            </div>
            <div className="flex items-center justify-between py-3 border-b border-white/10">
              <div className="flex items-center gap-3">
                <Mail className="w-5 h-5 text-slate-500" />
                <div>
                  <p className="text-sm font-medium text-slate-300">电子邮箱</p>
                  <p className="text-xs text-slate-500">{user?.email || '未设置邮箱'}</p>
                </div>
              </div>
              <button
                onClick={() => openEditor('email')}
                className="text-red-400 text-sm hover:text-red-300"
              >
                修改
              </button>
            </div>
            <div className="flex items-center justify-between py-3 border-b border-white/10">
              <div className="flex items-center gap-3">
                <Phone className="w-5 h-5 text-slate-500" />
                <div>
                  <p className="text-sm font-medium text-slate-300">手机号码</p>
                  <p className="text-xs text-slate-500">{user?.phone || '未设置手机号'}</p>
                </div>
              </div>
              <button
                onClick={() => openEditor('phone')}
                className="text-red-400 text-sm hover:text-red-300"
              >
                修改
              </button>
            </div>
            <div className="flex items-center justify-between py-3">
              <div className="flex items-center gap-3">
                <Lock className="w-5 h-5 text-slate-500" />
                <div>
                  <p className="text-sm font-medium text-slate-300">登录密码</p>
                </div>
              </div>
              <button
                onClick={() => openEditor('password')}
                className="text-red-400 text-sm hover:text-red-300"
              >
                修改
              </button>
            </div>
          </div>
        </div>

        {/* 今日使用配额 */}
        {quotaData && (
          <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-white">今日使用额度</h3>
              <span className={`text-xs px-2 py-0.5 rounded-full bg-gradient-to-r ${currentTierConfig.color} text-white`}>
                {currentTierConfig.label}
              </span>
            </div>
            <div className="grid gap-4">
              {quotaData.quota?.analysis_per_day !== undefined && renderQuotaBar(
                '深度分析',
                quotaData.quota.analysis_per_day.used,
                quotaData.quota.analysis_per_day.limit
              )}
              {quotaData.quota?.chat_per_day !== undefined && renderQuotaBar(
                '智能问答',
                quotaData.quota.chat_per_day.used,
                quotaData.quota.chat_per_day.limit
              )}
            </div>
          </div>
        )}

        {/* 会员升级 */}
        <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-white/10 p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-5">
            <Star className="w-5 h-5 text-amber-400" />
            <h3 className="text-lg font-bold text-white">会员计划</h3>
          </div>
          {upgradeMsg && (
            <div className={`mb-4 text-sm px-3 py-2 rounded-lg ${upgradeMsg.includes('失败') ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-green-500/10 text-green-400 border border-green-500/20'}`}>
              {upgradeMsg}
            </div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { key: 'free', label: '免费版', price: '¥0', desc: '基础投资分析功能', features: ['每日5次深度分析', '每日20次智能问答', '基础行情数据'] },
              { key: 'pro', label: '专业版', price: '¥29/月', desc: '适合活跃投资者', features: ['每日30次深度分析', '每日100次智能问答', '实时行情 + 新闻聚合'], popular: true },
              { key: 'premium', label: '旗舰版', price: '¥99/月', desc: '面向专业投研用户', features: ['每日100次深度分析', '每日500次智能问答', '全部功能无限制'] },
            ].map((plan) => {
              const isActive = currentTier === plan.key;
              const cfg = tierConfig[plan.key];
              const PlanIcon = cfg.icon;
              return (
                <div
                  key={plan.key}
                  className={`relative rounded-xl border p-5 transition-all duration-300 ${
                    isActive
                      ? `${cfg.borderColor} bg-gradient-to-b from-slate-800/80 to-slate-900/80 shadow-lg`
                      : 'border-white/5 bg-slate-800/30 hover:border-white/15 hover:bg-slate-800/50'
                  }`}
                >
                  {plan.popular && !isActive && (
                    <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-gradient-to-r from-blue-500 to-cyan-500 text-white text-[10px] font-bold rounded-full uppercase tracking-wider">
                      推荐
                    </div>
                  )}
                  {isActive && (
                    <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-gradient-to-r from-green-500 to-emerald-500 text-white text-[10px] font-bold rounded-full">
                      当前方案
                    </div>
                  )}
                  <div className="flex items-center gap-2 mb-3 mt-1">
                    <PlanIcon className={`w-4 h-4 ${cfg.textColor}`} />
                    <span className={`text-sm font-bold ${cfg.textColor}`}>{plan.label}</span>
                  </div>
                  <div className="text-2xl font-bold text-white mb-1">{plan.price}</div>
                  <p className="text-xs text-slate-500 mb-4">{plan.desc}</p>
                  <ul className="space-y-2 mb-5">
                    {plan.features.map((f, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-slate-300">
                        <Shield className="w-3.5 h-3.5 mt-0.5 text-slate-500 shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>
                  <button
                    onClick={() => handleUpgrade(plan.key)}
                    disabled={isActive || isUpgrading}
                    className={`w-full py-2 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-slate-700/50 text-slate-500 cursor-default'
                        : `bg-gradient-to-r ${cfg.color} text-white hover:opacity-90 shadow-md`
                    }`}
                  >
                    {isActive ? '当前方案' : isUpgrading ? '处理中...' : '升级'}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {isEditing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm">
          <div className="w-full max-w-lg bg-slate-900 border border-white/10 rounded-2xl p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-4">修改账户信息</h3>
            {editMode === 'nickname' && (
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">昵称</label>
                  <input
                    ref={nicknameRef}
                    type="text"
                    value={nickname}
                    onChange={(event) => setNickname(event.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-sm rounded-md p-2 text-slate-200"
                    placeholder="请输入昵称"
                  />
                </div>
                {error && <div className="text-sm text-red-400">{error}</div>}
              </div>
            )}
            {editMode === 'email' && (
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">邮箱</label>
                  <input
                    ref={emailRef}
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-sm rounded-md p-2 text-slate-200"
                    placeholder="请输入邮箱"
                  />
                </div>
                {error && <div className="text-sm text-red-400">{error}</div>}
              </div>
            )}
            {editMode === 'phone' && (
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">手机号</label>
                  <input
                    ref={phoneRef}
                    type="text"
                    value={phone}
                    onChange={(event) => setPhone(event.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-sm rounded-md p-2 text-slate-200"
                    placeholder="请输入手机号"
                  />
                </div>
                {error && <div className="text-sm text-red-400">{error}</div>}
              </div>
            )}
            {editMode === 'password' && (
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">原密码</label>
                  <input
                    ref={currentPasswordRef}
                    type="password"
                    value={currentPassword}
                    onChange={(event) => setCurrentPassword(event.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-sm rounded-md p-2 text-slate-200"
                    placeholder="请输入原密码"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">新密码</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-sm rounded-md p-2 text-slate-200"
                    placeholder="请输入新密码"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500 uppercase font-bold mb-2 block">确认新密码</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 text-sm rounded-md p-2 text-slate-200"
                    placeholder="请再次输入新密码"
                  />
                </div>
                {error && <div className="text-sm text-red-400">{error}</div>}
              </div>
            )}
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={closeEditor}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-sm"
                disabled={isSaving}
              >
                取消
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium"
                disabled={isSaving}
              >
                {isSaving ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfileView;
