import React, { useState } from 'react';
import { login, register } from '../../services/apiClient';

const AuthView = ({ viewState, setViewState, onAuthSuccess }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const isLogin = viewState === 'login';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    setSuccess('');

    try {
      if (isLogin) {
        const result = await login(username, password);
        setSuccess('登录成功, 正在跳转...');
        if (onAuthSuccess) {
          setTimeout(() => onAuthSuccess(result.token), 1200);
        }
      } else {
        const result = await register(username, password, email);
        setSuccess('注册成功, 正在跳转...');
        if (onAuthSuccess) {
          setTimeout(() => onAuthSuccess(result.token), 1200);
        }
      }
    } catch (err) {
      setError(err.message || '请求失败');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      background: 'var(--bg)',
    }}>
      <div style={{
        background: 'var(--card)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '40px 36px',
        width: '100%',
        maxWidth: 400,
      }}>
        <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8, textAlign: 'center' }}>
          {isLogin ? '登录' : '注册'}
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text3)', textAlign: 'center', marginBottom: 32 }}>
          {isLogin ? '登录后开始 AI 投资研究' : '创建账户, 开始智能投资分析'}
        </p>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: 'var(--text2)', marginBottom: 6 }}>
              用户名
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="请输入用户名"
              style={{ width: '100%' }}
              required
            />
          </div>

          {!isLogin && (
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: 'var(--text2)', marginBottom: 6 }}>
                邮箱
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="请输入邮箱"
                style={{ width: '100%' }}
                required
              />
            </div>
          )}

          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: 'var(--text2)', marginBottom: 6 }}>
              密码
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="请输入密码"
              style={{ width: '100%' }}
              required
            />
          </div>

          {error && (
            <div style={{
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
              borderRadius: 8,
              padding: '10px 14px',
              color: 'var(--red-bright)',
              fontSize: 13,
              marginBottom: 16,
            }}>
              {error}
            </div>
          )}

          {success && (
            <div style={{
              background: 'rgba(34, 197, 94, 0.1)',
              border: '1px solid rgba(34, 197, 94, 0.2)',
              borderRadius: 8,
              padding: '10px 14px',
              color: 'var(--green)',
              fontSize: 13,
              marginBottom: 16,
            }}>
              {success}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            style={{
              width: '100%', padding: 12, borderRadius: 8, fontSize: 15, fontWeight: 600,
              background: 'linear-gradient(135deg, var(--red), var(--orange))', color: '#fff',
              marginTop: 8, opacity: isLoading ? 0.7 : 1,
            }}
          >
            {isLoading ? '正在处理...' : (isLogin ? '登录' : '注册')}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: 'var(--text3)' }}>
          {isLogin ? (
            <span>
              没有账户?{' '}
              <button
                onClick={() => { setViewState('register'); setError(''); setSuccess(''); }}
                style={{ background: 'none', color: 'var(--red)', fontSize: 13, fontWeight: 500 }}
              >
                立即注册
              </button>
            </span>
          ) : (
            <span>
              已有账户?{' '}
              <button
                onClick={() => { setViewState('login'); setError(''); setSuccess(''); }}
                style={{ background: 'none', color: 'var(--red)', fontSize: 13, fontWeight: 500 }}
              >
                去登录
              </button>
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default AuthView;
