import React, { useState, useEffect } from 'react';
import { getAuthToken, getChatSessions } from '../../services/apiClient';

const HistoryView = ({ onNavigate }) => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadSessions = async () => {
      if (!getAuthToken()) {
        setLoading(false);
        return;
      }
      try {
        const data = await getChatSessions();
        setSessions(data.sessions || []);
      } catch {
        setSessions([]);
      } finally {
        setLoading(false);
      }
    };
    loadSessions();
  }, []);

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 32, letterSpacing: '-0.02em' }}>历史研究</h1>
        <div style={{ textAlign: 'center', padding: '80px 0', color: 'var(--text3)' }}>加载中...</div>
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 32, letterSpacing: '-0.02em' }}>历史研究</h1>

      {sessions.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <p style={{ color: 'var(--text3)', fontSize: 16 }}>暂无研究记录</p>
          <button
            onClick={() => onNavigate('research')}
            style={{
              marginTop: 20, padding: '12px 32px', borderRadius: 8, fontSize: 15, fontWeight: 600,
              background: 'linear-gradient(135deg, var(--red), var(--orange))', color: '#fff',
            }}
          >
            开始第一次研究
          </button>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: 16,
        }}>
          {sessions.map((session) => (
            <div
              key={session.session_id}
              className="history-card"
              onClick={() => onNavigate('research')}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                <h3 style={{ fontSize: 16, fontWeight: 600 }}>
                  {session.query || '—'}
                </h3>
                <span style={{ fontSize: 12, color: 'var(--text3)', fontFamily: 'ui-monospace, monospace' }}>
                  {formatDate(session.created_at).split(' ')[0]}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--text3)', marginBottom: 12 }}>
                <span>{session.turn_count ? `${session.turn_count} 轮研究` : '—'}</span>
                <span>·</span>
                <span>{session.asset || '—'}</span>
              </div>
              <p style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 12, lineHeight: 1.5 }}>
                {session.query || ''}
              </p>
              <div style={{ display: 'flex', gap: 6 }}>
                <span className="v2-tag">{session.risk_pref || '—'}</span>
                <span className="v2-tag">{session.period || '—'}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default HistoryView;
