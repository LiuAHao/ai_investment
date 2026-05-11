import React, { useState, useEffect } from 'react';
import { TrendingUp } from 'lucide-react';
import LandingView from './components/views/LandingView';
import AuthView from './components/views/AuthView';
import SettingsView from './components/views/SettingsView';
import HistoryView from './components/views/HistoryView';
import ResearchChatView from './components/research/ResearchChatView';
import { FeedbackProvider } from './contexts/FeedbackContext';
import ToastContainer from './components/ui/ToastContainer';
import {
  getAuthToken,
  setAuthToken,
  fetchProfile,
} from './services/apiClient';
import './App.css';

export default function InvestmentAgentApp() {
  const [viewState, setViewState] = useState('home');
  const [currentUser, setCurrentUser] = useState(null);

  useEffect(() => {
    const initAuth = async () => {
      const token = getAuthToken();
      if (!token) return;
      try {
        const profile = await fetchProfile();
        setCurrentUser(profile);
      } catch {
        setAuthToken(null);
      }
    };
    initAuth();
  }, []);

  const handleLogout = () => {
    setViewState('home');
    setCurrentUser(null);
    setAuthToken(null);
  };

  const handleAuthSuccess = async (token) => {
    setAuthToken(token);
    try {
      const profile = await fetchProfile();
      setCurrentUser(profile);
      setViewState('research');
    } catch {
      setAuthToken(null);
    }
  };

  const isAppLayout = ['research', 'history', 'settings'].includes(viewState);

  return (
    <FeedbackProvider>
      <div style={{ minHeight: '100%', display: 'flex', flexDirection: 'column' }}>

      {/* Home page - standalone layout */}
      {viewState === 'home' && (
        <LandingView
          currentUser={currentUser}
          onNavigate={setViewState}
          onLogout={handleLogout}
        />
      )}

      {/* Auth pages - standalone layout */}
      {(viewState === 'login' || viewState === 'register') && (
        <AuthView
          viewState={viewState}
          setViewState={setViewState}
          onAuthSuccess={handleAuthSuccess}
        />
      )}

      {/* App pages - shared header layout */}
      {isAppLayout && (
        <>
          <header className="v2-header">
            <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }} onClick={() => setViewState('home')}>
                <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                  <rect width="28" height="28" rx="6" fill="url(#lg)" />
                  <path d="M8 20V8l6 6 6-6v12" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                  <defs>
                    <linearGradient id="lg" x1="0" y1="0" x2="28" y2="28">
                      <stop stopColor="#dc2626" />
                      <stop offset="1" stopColor="#f97316" />
                    </linearGradient>
                  </defs>
                </svg>
                <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: '-0.01em' }}>AI 投资研究</span>
              </div>

              <nav style={{ display: 'flex', gap: 4 }}>
                {[
                  ['home', '首页'],
                  ['research', '研究'],
                  ['history', '历史'],
                  ['settings', '设置'],
                ].map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setViewState(key)}
                    style={{
                      padding: '6px 14px',
                      borderRadius: 6,
                      fontSize: 13,
                      fontWeight: 500,
                      color: viewState === key ? 'var(--text)' : 'var(--text3)',
                      background: viewState === key ? 'rgba(220, 38, 38, 0.12)' : 'transparent',
                    }}
                  >
                    {label}
                  </button>
                ))}
              </nav>

              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {currentUser ? (
                  <>
                    <span style={{ fontSize: 13, color: 'var(--text2)' }}>
                      {currentUser.nickname || currentUser.username}
                    </span>
                    <button
                      onClick={handleLogout}
                      style={{
                        padding: '6px 16px',
                        borderRadius: 6,
                        fontSize: 13,
                        color: 'var(--text2)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      退出
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => setViewState('login')}
                      style={{
                        padding: '6px 16px',
                        borderRadius: 6,
                        fontSize: 13,
                        color: 'var(--text2)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      登录
                    </button>
                    <button
                      onClick={() => setViewState('research')}
                      style={{
                        padding: '6px 16px',
                        borderRadius: 6,
                        fontSize: 13,
                        fontWeight: 600,
                        background: 'linear-gradient(135deg, var(--red), var(--orange))',
                        color: '#fff',
                      }}
                    >
                      开始研究
                    </button>
                  </>
                )}
              </div>
            </div>
          </header>

          <main style={{ flex: 1, maxWidth: viewState === 'research' ? 'none' : 1200, margin: '0 auto', padding: viewState === 'research' ? 0 : '32px 24px 80px', width: '100%' }}>
            {viewState === 'research' && <ResearchChatView />}
            {viewState === 'history' && <HistoryView onNavigate={setViewState} />}
            {viewState === 'settings' && <SettingsView />}
          </main>
        </>
      )}
      </div>
      <ToastContainer />
    </FeedbackProvider>
  );
}
