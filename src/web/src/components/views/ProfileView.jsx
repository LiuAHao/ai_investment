import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, Mail, Phone, Lock, User } from 'lucide-react';
import { updatePassword, updatePhone, updateProfile } from '../../services/apiClient';

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
              <h2 className="text-2xl font-bold text-white mb-2">{user?.nickname || user?.username || '用户'}</h2>
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
